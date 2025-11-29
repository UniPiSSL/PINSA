'use strict';

const { WorkloadModuleBase } = require('@hyperledger/caliper-core');

class InitLedgerWorkload extends WorkloadModuleBase {
    async submitTransaction() {
        await this.sutAdapter.sendRequests({
            contractId: 'basic',
            contractFunction: 'InitLedger',
            invokerIdentity: 'User1',
            readOnly: false
        });
    }
}

function createWorkloadModule() {
    return new InitLedgerWorkload();
}

module.exports.createWorkloadModule = createWorkloadModule;