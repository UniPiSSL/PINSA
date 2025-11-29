'use strict';

const { WorkloadModuleBase } = require('@hyperledger/caliper-core');

class DeletePolicyholderWorkload extends WorkloadModuleBase {
    constructor() {
        super();
        this.txIndex = 0;
    }

    async submitTransaction() {
        this.txIndex++;

        const args = this.roundArguments;

        // Use the same ID format as createPolicyholder
        const policyholderID = `${args.policyholderID}${this.workerIndex}_${this.txIndex}`;
        const insurancecompanyID = `${args.insurancecompanyID}${this.workerIndex}_${this.txIndex}`;

        const key = `${policyholderID}:${insurancecompanyID}`;

        try {
            await this.sutAdapter.sendRequests({
                contractId: 'basic',
                contractFunction: 'DeletePolicyholder',
                invokerIdentity: 'User1',
                contractArguments: [policyholderID, insurancecompanyID],
                readOnly: false
            });
        } catch (err) {
            console.error(`DeletePolicyholder failed for ${key}: ${err}`);
        }
    }
}

function createWorkloadModule() {
    return new DeletePolicyholderWorkload();
}

module.exports.createWorkloadModule = createWorkloadModule;
