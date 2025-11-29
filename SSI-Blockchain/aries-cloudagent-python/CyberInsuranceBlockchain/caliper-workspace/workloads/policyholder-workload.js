'use strict';

const { WorkloadModuleBase } = require('@hyperledger/caliper-core');

class PolicyholderWorkload extends WorkloadModuleBase {
    constructor() {
        super();
        this.txIndex = 0;
    }

    async initializeWorkloadModule(workerIndex, totalWorkers, roundIndex, roundLabel, sutAdapter, sutArgs) {
        console.log(`Worker ${workerIndex} initialized for round ${roundLabel}`);
    }

    async submitTransaction() {
        const functions = [
            'CreatePolicyholder',
            'ReadPolicyholder',
            'UpdatePolicyholder',
            'DeletePolicyholder',
            'AnalyzeContract',
            'CheckObligations',
            'ReportIncident',
            'ResponseIncident',
        ];

        const fn = functions[Math.floor(Math.random() * functions.length)];

        const phID = 'Pol' + ((this.txIndex % 1000) + 1).toString().padStart(3, '0');
        const icID = 'Ins' + ((this.txIndex % 100) + 1).toString().padStart(3, '0');
        let args = [];

        switch (fn) {
            case 'CreatePolicyholder':
                args = [
                    phID, icID,
                    '100000', '1000000', '10000',
                    '20250101', '20251231',
                    'legalaction-lostdevice-hacker',
                    'penetrationtests,stafftraining,backup-5,3,2',
                    'penetrationtests,stafftraining,backup-5,3,2'
                ];
                break;

            case 'UpdatePolicyholder':
                args = [phID, icID, 'HIGH', '500000'];
                break;

            case 'ReportIncident':
                args = [phID, icID, 'Inc' + this.txIndex, 'ransomware', '15000'];
                break;

            case 'ResponseIncident':
                args = [phID, icID, 'Inc' + this.txIndex];
                break;

            default:
                args = [phID, icID];
                break;
        }

        this.txIndex++;

        return this.sutAdapter.sendRequests({
            contractId: 'basic',
            contractFunction: fn,
            invokerIdentity: 'Admin1',
            contractArguments: args
        });
    }

    async cleanupWorkloadModule() {
        console.log('Workload complete.');
    }
}

function createWorkloadModule() {
    return new PolicyholderWorkload();
}

module.exports.createWorkloadModule = createWorkloadModule;
