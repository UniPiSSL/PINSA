'use strict';

const { WorkloadModuleBase } = require('@hyperledger/caliper-core');

class FullAssetWorkload extends WorkloadModuleBase {

    constructor() {
        super();
        this.policyholders = [];
    }

    async initializeWorkloadModule(workerIndex, totalWorkers, roundIndex, roundArguments, sutAdapter, sutContext) {
        await super.initializeWorkloadModule(workerIndex, totalWorkers, roundIndex, roundArguments, sutAdapter, sutContext);

        this.workerIndex = workerIndex;
        this.functionName = roundArguments.function;
        this.contractId = roundArguments.contractId || 'basic';
        this.identity = roundArguments.identity || 'Admin';
        this.assets = roundArguments.assets || 50;

        // Pre-generate policyholders for this worker
        for (let i = 0; i < this.assets; i++) {
            const id = `Pol${workerIndex}_${i}`;
            const company = `Ins${workerIndex}_${i}`;
            this.policyholders.push({ id, company });
        }
    }

    async submitTransaction() {
        if (this.policyholders.length === 0) {
            console.log("No policyholders available yet, skipping transaction");
            return;
        }

        const randomIndex = Math.floor(Math.random() * this.policyholders.length);
        const policyholder = this.policyholders[randomIndex];

        let args;
        switch (this.functionName) {
            case 'CreatePolicyholder':
                args = [
                    policyholder.id,
                    policyholder.company,
                    '100000',
                    '1000000',
                    '10000',
                    '20231001',
                    '20241001',
                    'legalaction-lostdevice',
                    'penetrationtests,stafftraining-5,5',
                    'penetrationtests,stafftraining-5,5'
                ];
                break;

            case 'ReadPolicyholder':
            case 'UpdatePolicyholder':
            case 'AnalyzeContract':
            case 'CheckObligations':
                args = [policyholder.id, policyholder.company];
                if (this.functionName === 'UpdatePolicyholder') {
                    args.push('Medium', '50000');
                }
                break;

            default:
                console.log(`Unknown function: ${this.functionName}`);
                return;
        }

        const request = {
            contractId: this.contractId,
            contractFunction: this.functionName,
            invokerIdentity: this.identity,
            contractArguments: args,
            readOnly: (this.functionName === 'ReadPolicyholder' || this.functionName === 'AnalyzeContract')
        };

        await this.sendRequestWithRetry(request);
    }

    async sendRequestWithRetry(request, retries = 3) {
        for (let attempt = 0; attempt < retries; attempt++) {
            try {
                await this.sutAdapter.sendRequests(request);
                return;
            } catch (err) {
                if (err.transactionCode === 'MVCC_READ_CONFLICT' && attempt < retries - 1) {
                    console.log(`MVCC conflict, retrying... (${attempt + 1})`);
                    await new Promise(r => setTimeout(r, 100));
                } else {
                    throw err;
                }
            }
        }
    }
}

function createWorkloadModule() {
    return new FullAssetWorkload();
}

module.exports.createWorkloadModule = createWorkloadModule;







