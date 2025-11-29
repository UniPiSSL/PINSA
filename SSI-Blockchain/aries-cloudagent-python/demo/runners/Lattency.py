import asyncio
import logging
import os
import random
import sys
import time
import string
import csv

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
# Latency measurement state
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


class BaseAgent(DemoAgent):
    def __init__(
        self,
        ident: str,
        port: int,
        prefix: str = None,
        **kwargs,
    ):
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
        #log_msg("handle_issue_credential - role = " + payload["role"] + " state = " + payload["state"])
        cred_ex_id = payload["credential_exchange_id"]
        self.credential_state[cred_ex_id] = payload["state"]
        self.credential_event.set()

    async def handle_issue_credential_v2_0(self, payload):
        #log_msg("handle_issue_credential_v2_0 - role = " + payload["role"] + " state = " + payload["state"] + " " + str(int(time.time())))
        #log_msg("handle_issue_credential_v2_0 - role = " + payload["role"] + " state = " + payload["state"])
        cred_ex_id = payload["cred_ex_id"]
        self.credential_state[cred_ex_id] = payload["state"]
        self.credential_event.set()

    async def handle_issue_credential_v2_0_indy(self, payload):
        #log_msg("handle_issue_credential_v2_0_indy - role = " + payload["role"] + " state = " + payload["state"])
        #log_msg("handle_issue_credential_v2_0_indy " + " " + str(int(time.time())))
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

            #log_msg(self.ident + " TOTAL=" + str(total) + " DICTIONARY= " + str(self.credential_state))

            for result in self.credential_state.values():
                if self.ident == 'Ncsa':
                    if result != "deleted" and result != "credential_acked":
                        pending += 1

                if self.ident == 'Policyholder':
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


class PolicyholderAgent(BaseAgent):
    def __init__(self, port: int, **kwargs):
        super().__init__("Policyholder", port, seed=None, **kwargs)
        self.extra_args = [
            "--auto-accept-invites",
            "--auto-accept-requests",
            "--auto-respond-credential-offer",
            "--auto-store-credential",
            "--monitor-ping",
            "--auto-respond-presentation-proposal",    #(den xrisimopioite)
            "--auto-respond-presentation-request",
        ]
        self.timing_log = "logs/policyholder_perf.log"

    async def fetch_credential_definition(self, cred_def_id):
        return await self.admin_GET(f"/credential-definitions/{cred_def_id}")

    async def propose_credential(
        self,
        cred_attrs: dict,
        cred_def_id: str,
        comment: str = None,
        auto_remove: bool = True,
    ):
        cred_preview = {
            "attributes": [{"name": n, "value": v} for (n, v) in cred_attrs.items()]
        }
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
        self.schema_id = None
        self.credential_definition_id = None
        self.revocation_registry_id = None

    async def publish_defs(self, support_revocation: bool = False):
        # create a schema
        self.log("Publishing test schema")
        version = format(
            "%d.%d.%d"
            % (random.randint(1, 101), random.randint(1, 101), random.randint(1, 101))
        )
        schema_body = {
            "schema_name": "ncsa schema",
            "schema_version": version,
            "attributes": [
                "policyholder_name",
                "date",
                "numberofbreaches",
                "riskfactor",
                "timestamp", 
                           
            ],
        }

        schema_response = await self.admin_POST("/schemas", schema_body)
        self.schema_id = schema_response["schema_id"]
        self.log(f"Schema ID: {self.schema_id}")

        # create a cred def for the schema
        self.log("Publishing test credential definition")
        credential_definition_body = {
            "schema_id": self.schema_id,
            "support_revocation": support_revocation,
            "revocation_registry_size": TAILS_FILE_COUNT,
        }
        credential_definition_response = await self.admin_POST(
            "/credential-definitions", credential_definition_body
        )
        self.credential_definition_id = credential_definition_response[
            "credential_definition_id"
        ]
        self.log(f"Credential Definition ID: {self.credential_definition_id}")

    async def send_credential(
        self, cred_attrs: dict, comment: str = None, auto_remove: bool = True
    ):
        cred_preview = {
            "@type": CRED_PREVIEW_TYPE,
            "attributes": [{"name": n, "value": v} for (n, v) in cred_attrs.items()],
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

    async def revoke_credential(self, cred_ex_id: str):
        await self.admin_POST(
            "/revocation/revoke",
            {
                "cred_ex_id": cred_ex_id,
                "publish": True,
            },
        )


def generate_random_string(length, use_uppercase=True, use_lowercase=True, use_digits=True, use_special=False):
    # Create a pool of characters based on the parameters
    char_pool = ''
    if use_uppercase:
        char_pool += string.ascii_uppercase  # A-Z
    if use_lowercase:
        char_pool += string.ascii_lowercase  # a-z
    if use_digits:
        char_pool += string.digits           # 0-9
    if use_special:
        char_pool += string.punctuation      # Special characters (!@#$%^&*, etc.)

    if not char_pool:
        raise ValueError("At least one character set must be enabled.")

    # Generate the random string
    random_string = ''.join(random.choices(char_pool, k=length))
    return random_string

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
    issue_count: int = 300,
    batch_size: int = 30,
    wallet_type: str = None,
    arg_file: str = None,
):

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
    policyholder_mediator_agent = None
    ncsa_mediator_agent = None
    run_timer = log_timer("Total runtime:")
    run_timer.start()

    try:
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

        with log_timer("Startup duration:"):
            await policyholder.start_process()
            await ncsa.start_process()

            if mediation:
                policyholder_mediator_agent = await start_mediator_agent(
                    start_port + 8, genesis, multi_ledger_config_path
                )
                if not policyholder_mediator_agent:
                    raise Exception("Mediator agent returns None :-(")
                ncsa_mediator_agent = await start_mediator_agent(
                    start_port + 11, genesis, multi_ledger_config_path
                )
                if not ncsa_mediator_agent:
                    raise Exception("Mediator agent returns None :-(")
            else:
                policyholder_mediator_agent = None
                ncsa_mediator_agent = None

        with log_timer("Connect duration:"):
            if multitenant:
                # create an initial managed sub-wallet (also mediated)
                await policyholder.register_or_switch_wallet(
                    "Policyholder.initial",
                    webhook_port=None,
                    mediator_agent=policyholder_mediator_agent,
                )
                await ncsa.register_or_switch_wallet(
                    "Ncsa.initial",
                    public_did=True,
                    webhook_port=None,
                    mediator_agent=ncsa_mediator_agent,
                )
            elif mediation:
                # we need to pre-connect the agent(s) to their mediator (use the same
                # mediator for both)
                if not await connect_wallet_to_mediator(policyholder, policyholder_mediator_agent):
                    log_msg("Mediation setup FAILED :-(")
                    raise Exception("Mediation setup FAILED :-(")
                if not await connect_wallet_to_mediator(ncsa, ncsa_mediator_agent):
                    log_msg("Mediation setup FAILED :-(")
                    raise Exception("Mediation setup FAILED :-(")

            invite = await ncsa.get_invite(use_did_exchange)
            await policyholder.receive_invite(invite["invitation"])
            await asyncio.wait_for(ncsa.detect_connection(), 30)

        if action != "ping":
            with log_timer("Publish duration:"):
                await ncsa.publish_defs(revocation)
            # cache the credential definition
            await policyholder.fetch_credential_definition(ncsa.credential_definition_id)

        if show_timing:
            await policyholder.reset_timing()
            await ncsa.reset_timing()
            if mediation:
                await policyholder_mediator_agent.reset_timing()
                await ncsa_mediator_agent.reset_timing()

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
            attributes = test_cred(index)
            asyncio.ensure_future(
                ncsa.send_credential(attributes, comment, not revocation)
            ).add_done_callback(done_send)

        async def check_received_creds(agent, issue_count, pb):
            reported = 0
            iter_pb = iter(pb) if pb else None
            while True:
                pending, total = await agent.check_received_creds()
                complete = total - pending
                if reported == complete:
                    await asyncio.wait_for(agent.update_creds(), 30)
                    continue
                # If complete increased, mark latency_end for newly completed indices
                if complete > reported:
                    # mark newly completed items: reported+1 .. complete (inclusive)
                    for idx_complete in range(reported + 1, complete + 1):
                        latency_end(idx_complete)

                if iter_pb and complete > reported:
                    try:
                        while next(iter_pb) < complete:
                            pass
                    except StopIteration:
                        iter_pb = None
                reported = complete
                if reported == issue_count:
                    break

        recv_timer = ncsa.log_timer(f"Completed {issue_count} credential exchanges in")
        recv_timer.start()

        with progress() as pb:
            receive_task = None

            try:
                receive_pg = pb(range(issue_count), label="Receiving credentials")
                check_received = check_received_creds
                send = send_credential
                completed = f"Done starting {issue_count} credential exchanges in"

                receive_task = asyncio.ensure_future(check_received(policyholder, issue_count, receive_pg))
                receive_task.add_done_callback(policyholder.check_task_exception)

                for idx in range(0, issue_count):
                    await send(idx + 1)

                await receive_task

            except KeyboardInterrupt:
                if receive_task:
                    receive_task.cancel()
                print("Cancelled")

        recv_timer.stop()

        # save CSV of latencies (only entries that completed)
        try:
            csv_name = "latency.csv"
            save_latency_csv(csv_name)
            # compute summary stats from LATENCY_DATA
            completed_latencies = [
                (rec["end"] - rec["start"])
                for rec in LATENCY_DATA.values()
                if rec.get("end") is not None
            ]
            if completed_latencies:
                avg_latency = sum(completed_latencies) / len(completed_latencies)
                min_latency = min(completed_latencies)
                max_latency = max(completed_latencies)
                # Print only the requested summary (Option B)
                print(f"Average latency: {avg_latency:.3f}s")
                print(f"Min latency: {min_latency:.3f}s")
                print(f"Max latency: {max_latency:.3f}s")
            else:
                print("No completed latency entries to summarize.")
            # show CSV absolute path for convenience
            try:
                abs_path = os.path.abspath(csv_name)
                print(f"Latency CSV saved as {abs_path}")
            except Exception:
                print(f"Latency CSV saved as {csv_name}")
        except Exception as e:
            log_msg(f"Failed saving latency CSV: {e}")

        avg = recv_timer.duration / issue_count
        item_short = "ping" if action == "ping" else "cred"
        item_long = "ping exchange" if action == "ping" else "credential"
        policyholder.log(f"Average time per {item_long}: {avg:.2f}s ({1/avg:.2f}/s)")

        log_msg("##############################")
        log_msg("##############################")
        time.sleep(2)
        log_msg("##############################")
        log_msg("##############################")

    finally:

        terminated = False
        """
        try:
            if policyholder:
                await policyholder.terminate()
        except Exception:
            LOGGER.exception("Error terminating agent:")
            terminated = False
        try:
            if ncsa:
                await ncsa.terminate()
        except Exception:
            LOGGER.exception("Error terminating agent:")
            terminated = False
        try:
            if policyholder_mediator_agent:
                await policyholder_mediator_agent.terminate()
            if ncsa_mediator_agent:
                await ncsa_mediator_agent.terminate()
        except Exception:
            LOGGER.exception("Error terminating agent:")
            terminated = False
        """
    run_timer.stop()
    await asyncio.sleep(0.1)

    if not terminated:
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
        default=300,
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
