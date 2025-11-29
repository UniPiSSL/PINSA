// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract PolicyholderInsurance {
    struct Incident {
        string incidentID;
        string incidentName;
        uint indemnification;
        uint status; // 1 = resolved, 2 = open
        string message;
    }

    struct KV {
        string name;
        uint value;
    }

    struct Policyholder {
        string PolicyholderID;
        string InsurancecompanyID;
        uint Premium;
        uint Limit;
        uint Deductible;
        string Risklevel;
        uint Totalmoneyrisk;
        uint Reputation;
        string[] Coverages;
        KV[] Obligations;
        KV[] Controls;
        Incident[] Incidents;
        bool exists;
    }

    mapping(bytes32 => Policyholder) private policyholders;
    bytes32[] private keys;

    event PolicyholderCreated(bytes32 key);
    event PolicyholderUpdated(bytes32 key);
    event PolicyholderDeleted(bytes32 key);
    event IncidentReported(bytes32 key, string incidentID);

    function _key(
        string memory policyholderID,
        string memory insurancecompanyID
    ) internal pure returns (bytes32) {
        return
            keccak256(
                abi.encodePacked(policyholderID, ":", insurancecompanyID)
            );
    }

    function _exists(bytes32 key) internal view returns (bool) {
        return policyholders[key].exists;
    }

    function _violate(Policyholder storage ph) internal {
        if (ph.Reputation > 0) ph.Reputation -= 1;
    }

    constructor() {
        // Initialize two policyholders (same as before)
        string[] memory coverages1 = new string[](3);
        coverages1[0] = "wiretransferfraud";
        coverages1[1] = "programmingerror";
        coverages1[2] = "staffmistake";

        Policyholder storage ph1 = policyholders[_key("Pol001", "Ins001")];
        ph1.PolicyholderID = "Pol001";
        ph1.InsurancecompanyID = "Ins001";
        ph1.Premium = 100000;
        ph1.Limit = 10000000;
        ph1.Deductible = 10000;
        ph1.Reputation = 100;
        ph1.Coverages = coverages1;
        ph1.exists = true;

        ph1.Obligations.push(KV("penetrationtests", 9));
        ph1.Obligations.push(KV("stafftraining", 9));
        ph1.Obligations.push(KV("backup", 9));

        ph1.Controls.push(KV("penetrationtests", 3));
        ph1.Controls.push(KV("stafftraining", 2));
        ph1.Controls.push(KV("backup", 1));

        ph1.Incidents.push(Incident("Inc001", "programmingerror", 1000, 2, ""));
        ph1.Incidents.push(Incident("Inc002", "legalaction", 1000, 2, ""));
        ph1.Incidents.push(Incident("Inc003", "ransomware", 16000, 2, ""));

        keys.push(_key("Pol001", "Ins001"));
        emit PolicyholderCreated(_key("Pol001", "Ins001"));

        string[] memory coverages2 = new string[](3);
        coverages2[0] = "legalaction";
        coverages2[1] = "lostdevice";
        coverages2[2] = "hacker";

        Policyholder storage ph2 = policyholders[_key("Pol002", "Ins002")];
        ph2.PolicyholderID = "Pol002";
        ph2.InsurancecompanyID = "Ins002";
        ph2.Premium = 800000;
        ph2.Limit = 8000000;
        ph2.Deductible = 8000;
        ph2.Reputation = 100;
        ph2.Coverages = coverages2;
        ph2.exists = true;

        ph2.Obligations.push(KV("penetrationtests", 8));
        ph2.Obligations.push(KV("stafftraining", 8));
        ph2.Obligations.push(KV("backup", 8));

        ph2.Controls.push(KV("penetrationtests", 8));
        ph2.Controls.push(KV("stafftraining", 8));
        ph2.Controls.push(KV("backup", 8));

        keys.push(_key("Pol002", "Ins002"));
        emit PolicyholderCreated(_key("Pol002", "Ins002"));
    }

    // ---------------- CRUD ----------------
    function createPolicyholder(
        string memory policyholderID,
        string memory insurancecompanyID,
        uint premium,
        uint limit_,
        uint deductible,
        string[] memory coverages,
        KV[] memory obligations,
        KV[] memory controls
    ) public {
        bytes32 key = _key(policyholderID, insurancecompanyID);
        require(!_exists(key), "Policyholder already exists");

        Policyholder storage ph = policyholders[key];
        ph.PolicyholderID = policyholderID;
        ph.InsurancecompanyID = insurancecompanyID;
        ph.Premium = premium;
        ph.Limit = limit_;
        ph.Deductible = deductible;
        ph.Reputation = 100;
        ph.Coverages = coverages;
        ph.exists = true;

        for (uint i = 0; i < obligations.length; i++)
            ph.Obligations.push(obligations[i]);
        for (uint i = 0; i < controls.length; i++)
            ph.Controls.push(controls[i]);

        keys.push(key);
        emit PolicyholderCreated(key);
    }
    function policyholderExists(
        string memory policyholderID,
        string memory insurancecompanyID
    ) public view returns (bool) {
        bytes32 key = _key(policyholderID, insurancecompanyID);
        return policyholders[key].exists;
    }
    function readPolicyholder(
        string memory policyholderID,
        string memory insurancecompanyID
    )
        public
        view
        returns (
            string memory,
            string memory,
            uint,
            uint,
            uint,
            uint,
            string[] memory,
            KV[] memory,
            KV[] memory,
            Incident[] memory
        )
    {
        bytes32 key = _key(policyholderID, insurancecompanyID);
        require(_exists(key), "Policyholder not found");
        Policyholder storage ph = policyholders[key];
        return (
            ph.PolicyholderID,
            ph.InsurancecompanyID,
            ph.Premium,
            ph.Limit,
            ph.Deductible,
            ph.Reputation,
            ph.Coverages,
            ph.Obligations,
            ph.Controls,
            ph.Incidents
        );
    }

    function updatePolicyholder(
        string memory policyholderID,
        string memory insurancecompanyID,
        string memory risklevel,
        uint totalmoneyrisk
    ) public {
        bytes32 key = _key(policyholderID, insurancecompanyID);
        require(_exists(key), "Policyholder not found");
        Policyholder storage ph = policyholders[key];
        ph.Risklevel = risklevel;
        ph.Totalmoneyrisk = totalmoneyrisk;
        emit PolicyholderUpdated(key);
    }

    function deletePolicyholder(
        string memory policyholderID,
        string memory insurancecompanyID
    ) public {
        bytes32 key = _key(policyholderID, insurancecompanyID);
        require(_exists(key), "Policyholder not found");
        delete policyholders[key];

        // Remove from keys array
        for (uint i = 0; i < keys.length; i++) {
            if (keys[i] == key) {
                keys[i] = keys[keys.length - 1];
                keys.pop();
                break;
            }
        }

        emit PolicyholderDeleted(key);
    }

    function getAllPolicyholders() public view returns (Policyholder[] memory) {
        Policyholder[] memory all = new Policyholder[](keys.length);
        for (uint i = 0; i < keys.length; i++) {
            all[i] = policyholders[keys[i]];
        }
        return all;
    }

    // ---------------- Incidents ----------------
    function reportIncident(
        string memory policyholderID,
        string memory insurancecompanyID,
        string memory incidentID,
        string memory incidentName,
        uint indemnification
    ) public {
        bytes32 key = _key(policyholderID, insurancecompanyID);
        require(_exists(key), "Policyholder not found");
        policyholders[key].Incidents.push(
            Incident(incidentID, incidentName, indemnification, 2, "")
        );
        emit IncidentReported(key, incidentID);
    }

    function resolveIncident(
        string memory policyholderID,
        string memory insurancecompanyID,
        string memory incidentID
    ) public returns (string memory) {
        bytes32 key = _key(policyholderID, insurancecompanyID);
        require(_exists(key), "Policyholder not found");
        Policyholder storage ph = policyholders[key];

        for (uint i = 0; i < ph.Incidents.length; i++) {
            Incident storage it = ph.Incidents[i];
            if (
                keccak256(bytes(it.incidentID)) == keccak256(bytes(incidentID))
            ) {
                if (it.status == 1) return "Incident already resolved";

                uint finalIndemn = it.indemnification > ph.Deductible
                    ? it.indemnification - ph.Deductible
                    : 0;
                if (finalIndemn > 0 && finalIndemn <= ph.Limit) {
                    ph.Limit -= finalIndemn;
                    it.message = "Incident resolved, limit reduced";
                } else {
                    it.message = "Incident resolved, limit unchanged";
                }

                it.status = 1;
                return it.message;
            }
        }
        return "Incident not found";
    }

    // ---------------- Contract Analysis ----------------
    function analyzeContract(
        string memory policyholderID,
        string memory insurancecompanyID
    ) public view returns (string[] memory, KV[] memory) {
        bytes32 key = _key(policyholderID, insurancecompanyID);
        require(_exists(key), "Policyholder not found");
        Policyholder storage ph = policyholders[key];
        return (ph.Coverages, ph.Obligations);
    }

    // ---------------- Check Obligations ----------------
    function checkObligations(
        string memory policyholderID,
        string memory insurancecompanyID
    ) public returns (bool) {
        bytes32 key = _key(policyholderID, insurancecompanyID);
        require(_exists(key), "Policyholder not found");
        Policyholder storage ph = policyholders[key];

        if (ph.Obligations.length != ph.Controls.length) {
            _violate(ph);
            return false;
        }

        for (uint i = 0; i < ph.Obligations.length; i++) {
            if (
                keccak256(bytes(ph.Obligations[i].name)) ==
                keccak256(bytes(ph.Controls[i].name))
            ) {
                if (ph.Obligations[i].value != ph.Controls[i].value) {
                    _violate(ph);
                    return false;
                }
            } else {
                _violate(ph);
                return false;
            }
        }

        return true;
    }
}
