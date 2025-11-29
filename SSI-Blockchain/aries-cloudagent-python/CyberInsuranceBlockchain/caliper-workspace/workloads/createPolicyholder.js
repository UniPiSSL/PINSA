'use strict';

const { WorkloadModuleBase } = require('@hyperledger/caliper-core');

class CreatePolicyholderWorkload extends WorkloadModuleBase {
    constructor() {
        super();
        this.txIndex = 0;
        this.timestamp = Date.now(); // unique per benchmark run
    }

    async initializeWorkloadModule(workerIndex, totalWorkers, roundIndex, roundArguments, sutAdapter, sutContext) {
        this.workerIndex = workerIndex;
        this.roundArguments = roundArguments;
        this.sutAdapter = sutAdapter;
    }

    async submitTransaction() {
        this.txIndex++;

        const args = this.roundArguments;

        // Generate truly unique IDs using base ID + worker index + txIndex + timestamp
        const policyholderID = `${args.policyholderID}_${this.workerIndex}_${this.txIndex}_${this.timestamp}`;
        const insurancecompanyID = `${args.insurancecompanyID}_${this.workerIndex}_${this.txIndex}_${this.timestamp}`;

        await this.sutAdapter.sendRequests({
            contractId: 'basic',
            contractFunction: 'CreatePolicyholder',
            invokerIdentity: 'User1',
            contractArguments: [
                policyholderID,
                insurancecompanyID,
                args.premium.toString(),
                args.limit.toString(),
                args.deductible.toString(),
                args.startdate.toString(),
                args.enddate.toString(),
                args.coverages,
                args.obligations,
                args.controls
            ],
            readOnly: false
        });
    }
}

function createWorkloadModule() {
    return new CreatePolicyholderWorkload();
}

module.exports.createWorkloadModule = createWorkloadModule;



