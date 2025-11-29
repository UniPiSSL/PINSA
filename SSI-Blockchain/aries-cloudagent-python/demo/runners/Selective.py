#!/usr/bin/env python3
import asyncio
import logging
import os
import random
import sys
import time
import string
import csv
import base64
import json

from typing import Tuple
from uuid import uuid4

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runners.support.agent import (  # noqa:E402
    DemoAgent,
    default_genesis_txns,
    start_mediator_agent,
    connect_wallet_to_mediator,
)
from runners.support.utils import (  # noqa:E402
    check_requires,
    log_msg,
    log_timer,
    progress,
)

CRED_PREVIEW_TYPE = "https://didcomm.org/issue-credential/2.0/credential-preview"
LOGGER = logging.getLogger(__name__)
TAILS_FILE_COUNT = int(os.getenv("TAILS_FILE_COUNT", 100))

# -------------------------
# Latency measurement statetrack_presentations
# -------------------------
LATENCY_DATA = {}  # index -> {"start": float, "end": float or None}


def latency_start(index: int):
    """Record the start timestamp for credential index."""
    LATENCY_DATA[index] = {"start": time.time(), "end": None}


def latency_end(index: int):
    """Record the end timestamp for credential index if start exists."""
    rec = LATENCY_DATA.get(index)
    if rec is not None and rec["end"] is None:
        rec["end"] = time.time()


def save_latency_csv(filename: str = "latency.csv"):
    """Write latency data to CSV (only entries that have an end timestamp)."""
    rows = []
    for idx in sorted(LATENCY_DATA.keys()):
        rec = LATENCY_DATA[idx]
        if rec["end"] is None:
            continue
        latency = rec["end"] - rec["start"]
        rows.append((idx, rec["start"], rec["end"], latency))
    with open(filename, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["index", "start_ts", "end_ts", "latency_seconds"])
        for r in rows:
            w.writerow(r)


ZKP_RESULTS = {"verified": 0, "failed": 0}


class BaseAgent(DemoAgent):
    def __init__(self, ident: str, port: int, prefix: str = None, **kwargs):
        if prefix is None:
            prefix = ident
        super().__init__(ident, port, port + 1, prefix=prefix, **kwargs)
        self._connection_id = None
        self._connection_ready = None
        self.credential_state = {}
        self.credential_event = asyncio.Event()
        self.revocations = []
        self.ping_state = {}
        self.ping_event = asyncio.Event()
        self.sent_pings = set()
        self.presentation_state = {}
        self.presentation_event = asyncio.Event()
        # presentation_attributes: dict of pres_ex_id -> {"revealed_attrs": {name: value}}
        self.presentation_attributes = {}

    @property
    def connection_id(self) -> str:
        return self._connection_id

    @connection_id.setter
    def connection_id(self, conn_id: str):
        self._connection_id = conn_id
        self._connection_ready = asyncio.Future()

    async def detect_connection(self):
        if not self._connection_ready:
            raise Exception("No connection to await")
        await self._connection_ready
        self._connection_ready = None

    async def handle_oob_invitation(self, message):
        pass

    async def handle_connections(self, payload):
        conn_id = payload["connection_id"]
        if (not self.connection_id) and (payload["state"] in ("invitation", "request")):
            self.connection_id = conn_id
        if conn_id == self.connection_id:
            if payload["state"] == "active" and not self._connection_ready.done():
                self.log("Connected")
                self._connection_ready.set_result(True)

    async def handle_issue_credential(self, payload):
        cred_ex_id = payload["credential_exchange_id"]
        self.credential_state[cred_ex_id] = payload["state"]
        self.credential_event.set()

    async def handle_issue_credential_v2_0(self, payload):
        cred_ex_id = payload["cred_ex_id"]
        self.credential_state[cred_ex_id] = payload["state"]
        self.credential_event.set()

    async def handle_issue_credential_v2_0_indy(self, payload):
        rev_reg_id = payload.get("rev_reg_id")
        cred_rev_id = payload.get("cred_rev_id")
        if rev_reg_id and cred_rev_id:
            self.revocations.append((rev_reg_id, cred_rev_id))

    async def handle_issuer_cred_rev(self, message):
        pass

    async def handle_ping(self, payload):
        thread_id = payload["thread_id"]
        if thread_id in self.sent_pings or (
            payload["state"] == "received"
            and payload.get("comment")
            and payload["comment"].startswith("test-ping")
        ):
            self.ping_state[thread_id] = payload["state"]
            self.ping_event.set()

    async def check_received_creds(self) -> Tuple[int, int]:
        """
        Returns (pending, total) where pending is number not completed.
        This method now works with global LATENCY_DATA marking for completed indices:
         - When the caller notices 'complete' increased, it will mark latency_end for newly completed items.
        """
        while True:
            self.credential_event.clear()
            pending = 0
            total = len(self.credential_state)

            for result in self.credential_state.values():
                if self.ident == "Ncsa":
                    if result != "deleted" and result != "credential_acked":
                        pending += 1
                if self.ident == "Policyholder":
                    if result != "done" and result != "credential_acked":
                        pending += 1

            if self.credential_event.is_set():
                continue
            return pending, total

    async def update_creds(self):
        await self.credential_event.wait()

    async def check_received_pings(self) -> Tuple[int, int]:
        while True:
            self.ping_event.clear()
            result = {}
            for thread_id, state in self.ping_state.items():
                if not result.get(state):
                    result[state] = set()
                result[state].add(thread_id)
            if self.ping_event.is_set():
                continue
            return result

    async def update_pings(self):
        await self.ping_event.wait()

    async def send_ping(self, ident: str = None) -> str:
        resp = await self.admin_POST(
            f"/connections/{self.connection_id}/send-ping",
            {"comment": f"test-ping {ident}"},
        )
        self.sent_pings.add(resp["thread_id"])

    def check_task_exception(self, fut: asyncio.Task):
        if fut.done():
            try:
                exc = fut.exception()
            except asyncio.CancelledError as e:
                exc = e
            if exc:
                self.log(f"Task raised exception: {str(exc)}")

  

async def check_received_presentations(agent: BaseAgent, count: int):
    """
    Return when 'count' presentations have been received (i.e., total - pending >= count).
    This mirrors the credential reception loop.
    """
    reported = 0
    while reported < count:
        pending = sum(
            1 for s in agent.presentation_state.values() if s not in ("verified", "presentation_ack", "done", "presentation_received", "presentation_acked")
        )
        total = len(agent.presentation_state)
        complete = total - pending
        if complete > reported:
            reported = complete
        if reported < count:
            await agent.update_presentations()
    return


class PolicyholderAgent(BaseAgent):
    def __init__(self, port: int, **kwargs):
        super().__init__("Policyholder", port, seed=None, **kwargs)

        # Auto-response flags for ACA-Py
        self.extra_args = [
            "--auto-accept-invites",
            "--auto-accept-requests",
            "--auto-respond-credential-offer",
            "--auto-store-credential",
            "--monitor-ping",
            "--auto-respond-presentation-request",
        ]

        # Store issued credentials keyed by attribute name
        self.issued_creds = {}

        # Track presentations received
        self.presentation_attributes = {}

        # Optional timing log
        self.timing_log = "logs/policyholder_perf.log"

    async def fetch_credential_definition(self, cred_def_id):
        return await self.admin_GET(f"/credential-definitions/{cred_def_id}")

    async def propose_credential(self, cred_attrs: dict, cred_def_id: str, comment: str = None, auto_remove: bool = True):
        """Send a credential proposal."""
        cred_preview = {"attributes": [{"name": n, "value": v} for n, v in cred_attrs.items()]}
        await self.admin_POST(
            "/issue-credential/send-proposal",
            {
                "connection_id": self.connection_id,
                "cred_def_id": cred_def_id,
                "credential_proposal": cred_preview,
                "comment": comment,
                "auto_remove": auto_remove,
            },
        )

    async def handle_issue_credential_v2_0(self, payload: dict):
        cred_ex_id = payload.get("cred_ex_id")
        self.credential_state[cred_ex_id] = payload.get("state")

        values = {}

        # 1. Try standard payload
        cred = payload.get("credential")
        if cred and "values" in cred:
            values = cred["values"]

        # 2. Fallback to proposal preview
        if not values:
            preview_attrs = payload.get("credential_proposal_dict", {}) \
                                .get("credential_preview", {}) \
                                .get("attributes", [])
            values = {a["name"]: {"raw": a["value"]} for a in preview_attrs}

        if values:
            # Store for selective disclosure
            await self.store_issued_credential({k: v["raw"] for k, v in values.items()})
            self.log(f"[Policyholder] Stored issued credentials: {self.issued_creds}")
        else:
            self.log(f"[Policyholder] No attributes found to store for credential {cred_ex_id}")

        self.credential_event.set()

    async def store_issued_credential(self, cred_attrs: dict):
        self.issued_creds.update(cred_attrs)
   




    async def handle_present_proof_v2_0(self, payload: dict):
        pres_ex_id = payload.get("pres_ex_id")
        attachments = payload.get("request_presentations~attach", [])

        if not pres_ex_id:
            self.log(f"[Policyholder] Received presentation with no pres_ex_id: {payload}")
            return

        # Try to find indy request in by_format if attachments missing
        if not attachments:
            by_format = payload.get("by_format", {}).get("pres_request", {})
            indy_data = by_format.get("indy")
            if indy_data:
                attachments = [
                    {"data": {"base64": base64.b64encode(json.dumps(indy_data).encode()).decode()}}
                ]

        if not attachments:
            self.log(f"[Policyholder] Received presentation request, no attachment needed: {pres_ex_id}")
            return

        # Decode proof request
        b64_data = attachments[0].get("data", {}).get("base64")
        if not b64_data:
            self.log(f"[Policyholder] No base64 data in proof request: {pres_ex_id}")
            return

        decoded = base64.b64decode(b64_data).decode("utf-8")
        proof_request = json.loads(decoded)
        requested_attrs = proof_request.get("requested_attributes", {})

        self.log(f"[Policyholder] Requested attributes for presentation {pres_ex_id}: {list(attr['name'] for attr in requested_attrs.values())}")
        self.log(f"[Policyholder] Currently issued creds: {self.issued_creds}")

        # Only include attributes you have
        presentation_attributes = {}
        for ref, attr in requested_attrs.items():
            name = attr["name"]
            if name in self.issued_creds:
                raw_value = self.issued_creds[name]
                encoded_value = str(int.from_bytes(raw_value.encode(), "big"))
                presentation_attributes[ref] = {"raw": raw_value, "encoded": encoded_value}

        if not presentation_attributes:
            self.log(f"[Policyholder] None of the requested attributes are available for presentation: {pres_ex_id}")
            return

        revealed_keys = [attr["raw"] for attr in presentation_attributes.values()]
        self.log(f"[Policyholder] Revealing attributes: {list(presentation_attributes.keys())} -> {revealed_keys}")

        # Track for auditing
        if not hasattr(self, "presentation_attributes"):
            self.presentation_attributes = {}
        self.presentation_attributes[pres_ex_id] = {"revealed_attrs": presentation_attributes}

        # Prepare Indy presentation
        indy_pres = {"requested_proof": {"revealed_attrs": presentation_attributes}}
        request = {
            "presentations~attach": [
                {"@id": "indy", "mime-type": "application/json", "data": {"json": indy_pres}}
            ]
        }

        # Send presentation
        await self.admin_POST(f"/present-proof-2.0/records/{pres_ex_id}/send-presentation", request)
        self.log(f"[Policyholder] Sent selective presentation: {list(presentation_attributes.keys())}")









class NcsaAgent(BaseAgent):
    def __init__(self, port: int, **kwargs):
        super().__init__("Ncsa", port, seed="random", **kwargs)
        self.extra_args = [
            "--auto-accept-invites",
            "--auto-accept-requests",
            "--monitor-ping",
            "--auto-respond-credential-proposal",
            "--auto-respond-credential-request",
            "--auto-verify-presentation",
        ]
        self.presentation_attributes = {}
        self.schema_id = None
        self.credential_definition_id = None
        self.revocation_registry_id = None

    async def publish_defs(self, support_revocation: bool = False):
        version = f"{random.randint(1,101)}.{random.randint(1,101)}.{random.randint(1,101)}"
        schema_body = {
            "schema_name": "ncsa schema",
            "schema_version": version,
            "attributes": ["policyholder_name", "date", "numberofbreaches", "riskfactor", "timestamp"],
        }
        schema_resp = await self.admin_POST("/schemas", schema_body)
        self.schema_id = schema_resp["schema_id"]
        self.log(f"Schema ID: {self.schema_id}")

        cred_def_body = {
            "schema_id": self.schema_id,
            "support_revocation": support_revocation,
            "revocation_registry_size": TAILS_FILE_COUNT,
        }
        cred_def_resp = await self.admin_POST("/credential-definitions", cred_def_body)
        self.credential_definition_id = cred_def_resp["credential_definition_id"]
        self.log(f"Credential Definition ID: {self.credential_definition_id}")

    async def send_credential(self, cred_attrs: dict, comment: str = None, auto_remove: bool = True):
        cred_preview = {
            "@type": CRED_PREVIEW_TYPE,
            "attributes": [{"name": n, "value": v} for n, v in cred_attrs.items()],
        }
        await self.admin_POST(
            "/issue-credential-2.0/send",
            {
                "filter": {"indy": {"cred_def_id": self.credential_definition_id}},
                "auto_remove": auto_remove,
                "comment": comment,
                "connection_id": self.connection_id,
                "credential_preview": cred_preview,
            },
        )

    async def request_selective_presentation(self, comment: str = None, requested_attr_names=None):
        # Only request these two attributes
        if requested_attr_names is None:
            requested_attr_names = ["policyholder_name", "numberofbreaches"]

        indy_proof = {
            "name": "SelectiveDisclosure",
            "version": "1.0",
            "requested_attributes": {
                f"attr{idx+1}_referent": {
                    "name": name,
                    "restrictions": [{"cred_def_id": self.credential_definition_id}]
                }
                for idx, name in enumerate(requested_attr_names)
            },
            "requested_predicates": {}
        }

        request = {
            "comment": comment,
            "connection_id": self.connection_id,
            "presentation_request": {"indy": indy_proof},

            "formats": [
                {
                    "attach_id": "indy",
                    "format": "hlindy-zkp-v2.0"
                }
            ],

            "request_presentations~attach": [
                {
                    "@id": "indy",
                    "mime-type": "application/json",
                    "data": {"json": indy_proof}
                }
            ]
        }

        try:
            await self.admin_POST("/present-proof-2.0/send-request", request)
            self.log(f"[Ncsa] Sent selective presentation request: {requested_attr_names}")
        except Exception as e:
            self.log(f"[Ncsa] Failed to send selective presentation request: {e}")

    async def handle_present_proof_v2_0(self, payload: dict):
        """
        Handle webhook for incoming presentation state updates.
        Log and store revealed attributes for reporting.
        """
        pres_ex_id = payload.get("pres_ex_id")
        revealed_attrs = {}

        # Check if the proof has a 'presentation' section (ACA-Py 2.0)
        presentation = payload.get("presentation", {})
        requested_proof = presentation.get("requested_proof", {})
        revealed = requested_proof.get("revealed_attrs", {})

        for ref, val in revealed.items():
            # val is usually {"raw": "value", "encoded": "..."}
            revealed_attrs[val.get("raw", ref)] = val.get("raw", "(unknown)")

        if pres_ex_id:
            self.presentation_attributes[pres_ex_id] = {"revealed_attrs": revealed_attrs}
            self.log(f"[Ncsa] Received proof for {pres_ex_id}: {revealed_attrs}")
    







def generate_random_string(length, use_uppercase=True, use_lowercase=True, use_digits=True, use_special=False):
    char_pool = ''
    if use_uppercase:
        char_pool += string.ascii_uppercase  # A-Z
    if use_lowercase:
        char_pool += string.ascii_lowercase  # a-z
    if use_digits:
        char_pool += string.digits           # 0-9
    if use_special:
        char_pool += string.punctuation      # Special characters

    if not char_pool:
        raise ValueError("At least one character set must be enabled.")

    random_string = ''.join(random.choices(char_pool, k=length))
    return random_string


async def track_presentations(agent: BaseAgent, count: int):
    """
    Track presentations and report revealed attributes for selective disclosure.
    """
    verified = 0
    failed = 0

    print("\n=== Presentation Details ===")
    # agent.presentation_attributes is a dict pres_ex_id -> {"revealed_attrs": {...}}
    for pres_id, payload in agent.presentation_attributes.items():
        revealed = payload.get("revealed_attrs", {}) if isinstance(payload, dict) else {}
        if revealed:
            revealed_str = ", ".join(f"{k}: {v}" for k, v in revealed.items())
            print(f"Presentation {pres_id}: Revealed attributes: {revealed_str}")
            verified += 1
        else:
            print(f"Presentation {pres_id}: No attributes revealed")
            failed += 1

    # Update global ZKP_RESULTS for reporting
    ZKP_RESULTS["verified"] = verified
    ZKP_RESULTS["failed"] = failed

    print("\n=== Presentation Summary ===")
    print(f"Total presentations requested: {count}")
    print(f"Verified presentations: {verified}")
    print(f"Failed presentations: {failed}")
    print("============================\n")


def check_attribute_privacy(agent: BaseAgent, total_attrs: int = 10):
    """
    Display all presentations with revealed attributes for selective disclosure.
    Prints in the same compact style as your screenshot: "Revealed X / Y attributes <list>"
    """
    print("\n=== Attribute Privacy Check ===")
    presentations = getattr(agent, "presentation_attributes", {})

    for pres_id, payload in presentations.items():
        revealed = payload.get("revealed_attrs", {}) if isinstance(payload, dict) else {}
        revealed_names = list(revealed.keys())
        revealed_count = len(revealed_names)
        revealed_str = ", ".join(revealed_names) if revealed_names else ""
        print(f"Presentation {pres_id}: Revealed {revealed_count} / {total_attrs} attributes {revealed_str}")

    total = len(presentations)
    print(f"Total presentations: {total}")
    print("===========================\n")


async def main(
    start_port: int,
    threads: int = 20,
    action: str = None,
    show_timing: bool = False,
    multitenant: bool = False,
    mediation: bool = False,
    multi_ledger: bool = False,
    use_did_exchange: bool = False,
    revocation: bool = False,
    tails_server_base_url: str = None,
    issue_count: int = 5,  # default small for demo
    batch_size: int = 30,
    wallet_type: str = None,
    arg_file: str = None,
):
    # --- Genesis / ledger setup ---
    if multi_ledger:
        genesis = None
        multi_ledger_config_path = "./demo/multi_ledger_config.yml"
    else:
        genesis = await default_genesis_txns()
        multi_ledger_config_path = None
        if not genesis:
            print("Error retrieving ledger genesis transactions")
            sys.exit(1)

    policyholder = None
    ncsa = None
    run_timer = log_timer("Total runtime:")
    run_timer.start()

    try:
        # --- Create agents ---
        policyholder = PolicyholderAgent(
            start_port,
            genesis_data=genesis,
            genesis_txn_list=multi_ledger_config_path,
            timing=show_timing,
            multitenant=multitenant,
            mediation=mediation,
            wallet_type=wallet_type,
            arg_file=arg_file,
        )
        await policyholder.listen_webhooks(start_port + 2)

        ncsa = NcsaAgent(
            start_port + 3,
            genesis_data=genesis,
            genesis_txn_list=multi_ledger_config_path,
            timing=show_timing,
            tails_server_base_url=tails_server_base_url,
            multitenant=multitenant,
            mediation=mediation,
            wallet_type=wallet_type,
            arg_file=arg_file,
        )
        await ncsa.listen_webhooks(start_port + 5)
        await ncsa.register_did()

        # --- Start agents ---
        await policyholder.start_process()
        await ncsa.start_process()

        # --- Connect agents ---
        invite = await ncsa.get_invite(use_did_exchange)
        await policyholder.receive_invite(invite["invitation"])
        await asyncio.wait_for(ncsa.detect_connection(), 30)

        # --- Publish schema & credential definitions ---
        if action != "ping":
            await ncsa.publish_defs(revocation)
            await policyholder.fetch_credential_definition(ncsa.credential_definition_id)

        # --- Concurrency semaphore for credential sending ---
        semaphore = asyncio.Semaphore(threads)

        def done_send(fut: asyncio.Task):
            semaphore.release()
            ncsa.check_task_exception(fut)

        def test_cred(index: int) -> dict:
            return {
                "policyholder_name": f"User {index}",
                "date": f"{2023}-{index:02d}-15",
                "numberofbreaches": str(random.randint(0, 50)),
                "riskfactor": str(random.randint(1, 100)),
                "timestamp": str(int(time.time())),
            }

        async def send_credential(index: int):
            latency_start(index)
            await semaphore.acquire()
            comment = f"issue test credential {index}"
            attrs = test_cred(index)
            asyncio.ensure_future(ncsa.send_credential(attrs, comment, not revocation)).add_done_callback(done_send)

        async def check_received_creds(agent, count):
            reported = 0
            while reported < count:
                pending, total = await agent.check_received_creds()
                complete = total - pending
                if complete > reported:
                    for idx in range(reported + 1, complete + 1):
                        latency_end(idx)
                    reported = complete
                if reported < count:
                    await agent.update_creds()

        # --- Start credential issuing ---
        recv_timer = ncsa.log_timer(f"Completed {issue_count} credential exchanges in")
        recv_timer.start()
        with progress() as pb:
            receive_task = asyncio.ensure_future(check_received_creds(policyholder, issue_count))
            for idx in range(1, issue_count + 1):
                await send_credential(idx)
            await receive_task
        recv_timer.stop()

        # --- Start presentation requests ---
        presentation_count = issue_count

        recv_pres_timer = ncsa.log_timer(f"Sent {presentation_count} selective presentation requests in")
        recv_pres_timer.start()

        # Send the requests in a loop and let the Policyholder auto-respond
        for i in range(1, presentation_count + 1):
            await ncsa.request_selective_presentation(
                comment=f"Selective proof {i}",
                requested_attr_names=["policyholder_name", "numberofbreaches"],
            )
            # small throttling to avoid overwhelming the agent in very fast loops
            await asyncio.sleep(0.05)

        recv_pres_timer.stop()

        # Wait for presentations to arrive (Ncsa will receive them and populate presentation_attributes)
        await check_received_presentations(ncsa, presentation_count)

        # --- Track and verify presentations ---
        await track_presentations(ncsa, presentation_count)

        # --- Check revealed attributes for privacy ---
        check_attribute_privacy(ncsa, total_attrs=10)

        # --- Summary dashboard ---
        print("\n=== Performance Summary ===")
        print(f"Credentials issued: {issue_count}")
        print(f"Presentations requested: {presentation_count}")
        print(f"Presentations verified (pass): {ZKP_RESULTS['verified']}")
        print(f"Presentations failed (fail): {ZKP_RESULTS['failed']}")
        print("============================\n")

        # --- Save latency CSV ---
        save_latency_csv("latency.csv")

    finally:
        terminated = False
        run_timer.stop()
        await asyncio.sleep(0.1)
        if not terminated:
            # exit with non-zero so the harness sees termination
            os._exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Runs an automated credential issuance performance demo."
    )
    parser.add_argument(
        "-c",
        "--count",
        type=int,
        default=5,
        help="Set the number of credentials to issue",
    )
    parser.add_argument(
        "-b",
        "--batch",
        type=int,
        default=100,
        help="Set the batch size of credentials to issue",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=8030,
        metavar=("<port>"),
        help="Choose the starting port number to listen on",
    )
    parser.add_argument(
        "--ping",
        action="store_true",
        default=False,
        help="Only send ping messages between the agents",
    )
    parser.add_argument(
        "--multitenant", action="store_true", help="Enable multitenancy options"
    )
    parser.add_argument(
        "--mediation", action="store_true", help="Enable mediation functionality"
    )
    parser.add_argument(
        "--multi-ledger",
        action="store_true",
        help=(
            "Enable multiple ledger mode, config file can be found "
            "here: ./demo/multi_ledger_config.yml"
        ),
    )
    parser.add_argument(
        "--did-exchange",
        action="store_true",
        help="Use DID-Exchange protocol for connections",
    )
    parser.add_argument(
        "--proposal",
        action="store_true",
        default=False,
        help="Start credential exchange with a credential proposal from Policyholder",
    )
    parser.add_argument(
        "--revocation", action="store_true", help="Enable credential revocation"
    )
    parser.add_argument(
        "--tails-server-base-url",
        type=str,
        metavar="<tails-server-base-url>",
        help="Tails server base url",
    )
    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=10,
        help="Set the number of concurrent exchanges to start",
    )
    parser.add_argument(
        "--timing", action="store_true", help="Enable detailed timing report"
    )
    parser.add_argument(
        "--wallet-type",
        type=str,
        metavar="<wallet-type>",
        help="Set the agent wallet type",
    )
    parser.add_argument(
        "--arg-file",
        type=str,
        metavar="<arg-file>",
        help="Specify a file containing additional aca-py parameters",
    )
    args = parser.parse_args()

    if args.did_exchange and args.mediation:
        raise Exception(
            "DID-Exchange connection protocol is not (yet) compatible with mediation"
        )

    tails_server_base_url = args.tails_server_base_url or os.getenv("PUBLIC_TAILS_URL")

    if args.revocation and not tails_server_base_url:
        raise Exception(
            "If revocation is enabled, --tails-server-base-url must be provided"
        )
    action = "issue"
    if args.proposal:
        action = "propose"
    if args.ping:
        action = "ping"

    check_requires(args)

    try:
        asyncio.get_event_loop().run_until_complete(
            main(
                args.port,
                args.threads,
                action,
                args.timing,
                args.multitenant,
                args.mediation,
                args.multi_ledger,
                args.did_exchange,
                args.revocation,
                tails_server_base_url,
                args.count,
                args.batch,
                args.wallet_type,
                args.arg_file,
            )
        )
    except KeyboardInterrupt:
        os._exit(1)
