'use strict';
const { WorkloadModuleBase } = require('@hyperledger/caliper-core');

class ReadPolicyholderWorkload extends WorkloadModuleBase {
    constructor() {
        super();
        this.txIndex = 0;
    }

    async initializeWorkloadModule(workerIndex, totalWorkers, roundIndex, roundArguments, sutAdapter, sutContext) {
        this.workerIndex = workerIndex;
        this.sutAdapter = sutAdapter;

        // Predefined keys that exist on the ledger
        // These should match exactly the keys already created
        this.keys = [
            { policyholderID: "PolX_7_9_1762944000890", insurancecompanyID: "InsX_7_9_1762944000890" },
            { policyholderID: "PolX_7_9_1762944021716", insurancecompanyID: "InsX_7_9_1762944021716" },
            { policyholderID: "PolX_7_9_1762944042964", insurancecompanyID: "InsX_7_9_1762944042964" },
            { policyholderID: "PolX_7_9_1762944067875", insurancecompanyID: "InsX_7_9_1762944067875" },
            { policyholderID: "PolX_7_9_1762944093443", insurancecompanyID: "InsX_7_9_1762944093443" },
            { policyholderID: "PolX_7_9_1762944125983", insurancecompanyID: "InsX_7_9_1762944125983" },
            { policyholderID: "PolX_7_9_1762944155198", insurancecompanyID: "InsX_7_9_1762944155198" },
            { policyholderID: "PolX_7_9_1762944188284", insurancecompanyID: "InsX_7_9_1762944188284" },
            { policyholderID: "PolX_7_9_1762944221465", insurancecompanyID: "InsX_7_9_1762944221465" },
            { policyholderID: "PolX_7_9_1762944266779", insurancecompanyID: "InsX_7_9_1762944266779" }
        ];
    }

    async submitTransaction() {
        this.txIndex++;

        // Pick a random key from the existing ledger entries
        const key = this.keys[Math.floor(Math.random() * this.keys.length)];

        await this.sutAdapter.sendRequests({
            contractId: 'basic',
            contractFunction: 'ReadPolicyholder',
            invokerIdentity: 'User1',
            contractArguments: [key.policyholderID, key.insurancecompanyID],
            readOnly: true
        });
    }
}

function createWorkloadModule() {
    return new ReadPolicyholderWorkload();
}

module.exports.createWorkloadModule = createWorkloadModule;


