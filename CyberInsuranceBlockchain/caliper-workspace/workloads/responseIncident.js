'use strict';

const { WorkloadModuleBase } = require('@hyperledger/caliper-core');
const fs = require('fs');
const path = require('path');

class ResponseIncidentWorkload extends WorkloadModuleBase {
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

        // Load policyholder data (assuming incidents exist)
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
        // Pick a random policyholder with at least one incident
        const policyholder = this.shuffledPolicyholders[this.txIndex % this.shuffledPolicyholders.length];
        this.txIndex++;

        // Pick an incident ID from this policyholder (if any)
        let incidentID = '';
        if (policyholder.Incidents && policyholder.Incidents.length > 0) {
            const incident = policyholder.Incidents[Math.floor(Math.random() * policyholder.Incidents.length)];
            incidentID = incident.incidentID || incident.incidentId || incident.IncidentID || 'Inc001';
        } else {
            // fallback if no incidents exist — you could skip or simulate one
            incidentID = `Inc${this.txIndex}`;
        }

        const request = {
            contractId: 'basic',
            contractFunction: 'ResponseIncident',
            invokerIdentity: 'User1',
            contractArguments: [
                policyholder.PolicyholderID,
                policyholder.InsurancecompanyID,
                incidentID
            ],
            readOnly: false
        };

        await this.sutAdapter.sendRequests(request);
    }
}

function createWorkloadModule() {
    return new ResponseIncidentWorkload();
}

module.exports.createWorkloadModule = createWorkloadModule;
