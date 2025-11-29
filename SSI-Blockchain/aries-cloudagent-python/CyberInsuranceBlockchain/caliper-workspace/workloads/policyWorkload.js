'use strict';

const { WorkloadModuleBase } = require('@hyperledger/caliper-core');

class PolicyWorkload extends WorkloadModuleBase {
    constructor() {
        super();
    }

    /**
     * Initialize the workload module
     */
    async initializeWorkloadModule(workerIndex, totalWorkers, roundIndex, roundArguments, sutAdapter, sutContext) {
        await super.initializeWorkloadModule(workerIndex, totalWorkers, roundIndex, roundArguments, sutAdapter, sutContext);

        console.log(`Worker ${workerIndex} initialized for round ${roundIndex}`);
    }

    /**
     * Submit a transaction dynamically based on YAML
     */
    async submitTransaction() {
        const func = this.roundArguments.function;
        const args = this.roundArguments.arguments || [];

        const request = {
            contractId: this.roundArguments.contractId,
            contractFunction: func,
            invokerIdentity: this.roundArguments.identity || 'Admin',
            contractArguments: Object.values(args), // ensures proper array
            readOnly: this.roundArguments.type === 'query'
        };

        await this.sendRequestWithRetry(request);
    }

    /**
     * Retry helper to handle MVCC_READ_CONFLICT
     */
    async sendRequestWithRetry(request, retries = 3) {
        for (let attempt = 0; attempt < retries; attempt++) {
            try {
                await this.sutAdapter.sendRequests(request);
                return;
            } catch (err) {
                if (err.transactionCode === 'MVCC_READ_CONFLICT' && attempt < retries - 1) {
                    console.log(`Worker ${this.workerIndex}: MVCC conflict for ${request.contractArguments[0]}, retrying... (${attempt + 1})`);
                    await new Promise(r => setTimeout(r, 100));
                } else {
                    throw err;
                }
            }
        }
    }
}

/**
 * Factory method required by Caliper
 */
function createWorkloadModule() {
    return new PolicyWorkload();
}

module.exports.createWorkloadModule = createWorkloadModule;
