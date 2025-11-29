'use strict';

const { WorkloadModuleBase } = require('@hyperledger/caliper-core');
const fs = require('fs');
const path = require('path');

class DeletePolicyholderWorkload extends WorkloadModuleBase {
    constructor() {
        super();
        this.txIndex = 0;
        this.policyholders = [];
        this.shuffledPolicyholders = [];
    }

    async initializeWorkloadModule(workerIndex, totalWorkers, roundIndex, roundArguments, sutAdapter, sutContext) {
        this.workerIndex = workerIndex;
        this.roundArguments = roundArguments;
        this.sutAdapter = sutAdapter;

        // Load initial policyholders
        const filePath = path.join(__dirname, 'policyholders.json');
        const data = fs.readFileSync(filePath, 'utf8');
        this.policyholders = JSON.parse(data);

        this.shufflePolicyholders();
    }

    shufflePolicyholders() {
        this.shuffledPolicyholders = [...this.policyholders];
        for (let i = this.shuffledPolicyholders.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [this.shuffledPolicyholders[i], this.shuffledPolicyholders[j]] = [this.shuffledPolicyholders[j], this.shuffledPolicyholders[i]];
        }
        this.txIndex = 0;
    }

    async submitTransaction() {
        // Select a random policyholder
        const policyholder = this.shuffledPolicyholders[this.txIndex % this.shuffledPolicyholders.length];
        this.txIndex++;

        const request = {
            contractId: 'basic',
            contractFunction: 'DeletePolicyholder',
            invokerIdentity: 'User1',
            contractArguments: [
                policyholder.PolicyholderID,
                policyholder.InsurancecompanyID
            ],
            readOnly: false
        };

        await this.sutAdapter.sendRequests(request);
    }
}

function createWorkloadModule() {
    return new DeletePolicyholderWorkload();
}

module.exports.createWorkloadModule = createWorkloadModule;
