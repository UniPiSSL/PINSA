'use strict';

const { WorkloadModuleBase } = require('@hyperledger/caliper-core');
const fs = require('fs');

class AnalyzeContractWorkload extends WorkloadModuleBase {
    constructor() {
        super();
        this.txIndex = 0;
    }

    async initializeWorkloadModule(workerIndex, totalWorkers, roundIndex, roundArguments, sutAdapter, sutContext) {
        this.workerIndex = workerIndex;
        this.sutAdapter = sutAdapter;

        // Load all policies from file (the ones you provided)
        this.policies = JSON.parse(fs.readFileSync('./policies.json'));
        if (!this.policies || this.policies.length === 0) {
            throw new Error('No policies found in policies.json');
        }
    }

    async submitTransaction() {
        this.txIndex++;

        // Pick a policy round-robin
        const policy = this.policies[this.txIndex % this.policies.length];

        await this.sutAdapter.sendRequests({
            contractId: 'basic',                  // change to your chaincode name
            contractFunction: 'AnalyzeContract',  // function to test
            invokerIdentity: 'User1',
            contractArguments: [
                policy.PolicyholderID,
                policy.InsurancecompanyID
            ],
            readOnly: true
        });
    }
}

function createWorkloadModule() {
    return new AnalyzeContractWorkload();
}

module.exports.createWorkloadModule = createWorkloadModule;

