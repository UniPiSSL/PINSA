'use strict';

module.exports.info  = 'Full Asset Advanced Workload';

let txIndex = 0;

module.exports.init = async function(workerIndex, totalWorkers, roundIndex, roundArguments, sutAdapter, sutContext) {
    // no init needed
};

module.exports.run = async function(workerIndex, roundIndex, roundArguments, sutAdapter, sutContext) {
    const id = txIndex++;
    const policyholderID = roundArguments.baseId + id;
    const insuranceID = roundArguments.insuranceBaseId + id;

    let args = [];
    switch(roundArguments.function) {
        case 'CreatePolicyholder':
            args = [
                policyholderID,
                insuranceID,
                roundArguments.premium,
                roundArguments.limit,
                roundArguments.deductible,
                roundArguments.startdate,
                roundArguments.enddate,
                roundArguments.coverages,
                roundArguments.obligations,
                roundArguments.controls
            ];
            break;
        case 'ReadPolicyholder':
        case 'DeletePolicyholder':
        case 'UpdatePolicyholder':
        case 'AnalyzeContract':
        case 'CheckObligations':
            args = [
                policyholderID,
                insuranceID
            ];
            if(roundArguments.function === 'UpdatePolicyholder') {
                args.push(roundArguments.risklevel, roundArguments.totalmoneyrisk);
            }
            break;
        case 'ReportIncident':
            args = [
                policyholderID,
                insuranceID,
                roundArguments.incidentID,
                roundArguments.incidentName,
                roundArguments.indemnification
            ];
            break;
        case 'ResponseIncident':
            args = [
                policyholderID,
                insuranceID,
                roundArguments.incidentID
            ];
            break;
        case 'InitLedger':
            args = [];
            break;
        default:
            throw new Error(`Unknown function: ${roundArguments.function}`);
    }

    const request = {
        contractId: roundArguments.contractId,
        contractFunction: roundArguments.function,
        invokerIdentity: 'Admin',
        contractArguments: args,
        readOnly: roundArguments.type === 'query'
    };

    return sutAdapter.sendRequests(request);
};

module.exports.end = async function() {
    // no cleanup
};
