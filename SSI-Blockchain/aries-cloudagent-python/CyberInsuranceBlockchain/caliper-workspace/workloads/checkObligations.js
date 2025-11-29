'use strict';

const { WorkloadModuleBase } = require('@hyperledger/caliper-core');
const fs = require('fs');
const path = require('path');

class CheckObligationsWorkload extends WorkloadModuleBase {
    constructor() {
        super();
        this.txIndex = 0;

        // Load policyholders from JSON file
        const filePath = path.join(__dirname, 'all_policyholders.json');
        this.policyholders = JSON.parse(fs.readFileSync(filePath, 'utf8'));

        this.shuffledPolicyholders = [];
    }

    async initializeWorkloadModule(workerIndex, totalWorkers, roundIndex, roundArguments, sutAdapter, sutContext) {
        this.workerIndex = workerIndex;
        this.roundArguments = roundArguments;
        this.sutAdapter = sutAdapter;

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

        // Pick next policyholder
        const policyholder = this.shuffledPolicyholders[this.txIndex % this.shuffledPolicyholders.length];
        this.txIndex++;

        // Reshuffle after a full cycle
        if (this.txIndex % this.shuffledPolicyholders.length === 0) {
            this.shufflePolicyholders();
        }

        await this.sutAdapter.sendRequests({
            contractId: 'basic',
            contractFunction: 'CheckObligations',
            invokerIdentity: 'User1',
            contractArguments: [
                policyholder.PolicyholderID,
                policyholder.InsurancecompanyID
            ],
            readOnly: false
        });
    }
}

function createWorkloadModule() {
    return new CheckObligationsWorkload();
}

module.exports.createWorkloadModule = createWorkloadModule;

