'use strict';

const { WorkloadModuleBase } = require('@hyperledger/caliper-core');
const fs = require('fs');
const path = require('path');

class CheckPolicyholderExistsWorkload extends WorkloadModuleBase {
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

        // Load policyholders from JSON file
        const filePath = path.join(__dirname, 'policyholders.json'); // JSON file in same directory
        const data = fs.readFileSync(filePath, 'utf8');
        this.policyholders = JSON.parse(data);

        // Shuffle policyholders for randomized access
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
        if (this.shuffledPolicyholders.length === 0) {
            throw new Error('No policyholders available to check');
        }

        // Pick a random policyholder
        const policyholder = this.shuffledPolicyholders[this.txIndex % this.shuffledPolicyholders.length];
        this.txIndex++;

        // Reshuffle when a full cycle is completed
        if (this.txIndex % this.shuffledPolicyholders.length === 0) {
            this.shufflePolicyholders();
        }

        await this.sutAdapter.sendRequests({
            contractId: 'basic',
            contractFunction: 'PolicyholderExists',
            invokerIdentity: 'User1',
            contractArguments: [
                policyholder.PolicyholderID,
                policyholder.InsurancecompanyID
            ],
            readOnly: true
        });
    }
}

function createWorkloadModule() {
    return new CheckPolicyholderExistsWorkload();
}

module.exports.createWorkloadModule = createWorkloadModule;

