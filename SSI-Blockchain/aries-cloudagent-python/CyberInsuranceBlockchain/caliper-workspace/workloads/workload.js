'use strict';

const { v4: uuidv4 } = require('uuid');

module.exports.info = {
    name: 'basic-workload',
    description: 'Mixed workload for the basic contract',
    version: '1.0.0'
};

let createdKeys = [];
let counter = 0;

module.exports.init = async function() {};

module.exports.run = async function(context) {
    const fns = [
        'CreatePolicyholder',
        'ReadPolicyholder',
        'UpdatePolicyholder',
        'GetAllPolicyholders',
        'AnalyzeContract',
        'CheckObligations',
        'ReportIncident',
        'ResponseIncident'
    ];

    const fcn = fns[Math.floor(Math.random() * fns.length)];

    let args = [];
    let key;

    switch (fcn) {
        case 'CreatePolicyholder':
            counter++;
            const policyholderID = 'Pol' + String(1000 + counter);
            const insurancecompanyID = 'Ins' + String(1000 + counter);
            key = `${policyholderID}:${insurancecompanyID}`;
            createdKeys.push(key);
            args = [
                policyholderID, insurancecompanyID,
                '10000', '1000000', '5000', '20230101', '20250101',
                'wiretransferfraud-programmingerror-staffmistake',
                'penetrationtests,stafftraining,backup-9,9,9',
                'penetrationtests,stafftraining,backup-9,9,9'
            ];
            break;

        case 'ReadPolicyholder':
            key = createdKeys.length ? createdKeys[Math.floor(Math.random() * createdKeys.length)] : 'Pol001:Ins001';
            args = key.split(':');
            break;

        case 'UpdatePolicyholder':
            key = createdKeys.length ? createdKeys[Math.floor(Math.random() * createdKeys.length)] : 'Pol001:Ins001';
            args = [...key.split(':'), 'MEDIUM', String(Math.floor(Math.random() * 100000))];
            break;

        case 'GetAllPolicyholders':
            args = [];
            break;

        case 'AnalyzeContract':
        case 'CheckObligations':
        case 'GetPolicyholderHistory':
            key = createdKeys.length ? createdKeys[Math.floor(Math.random() * createdKeys.length)] : 'Pol001:Ins001';
            args = key.split(':');
            break;

        case 'ReportIncident':
            key = createdKeys.length ? createdKeys[Math.floor(Math.random() * createdKeys.length)] : 'Pol001:Ins001';
            args = [...key.split(':'), uuidv4().substring(0, 6), 'ransomware', '50000'];
            break;

        case 'ResponseIncident':
            key = createdKeys.length ? createdKeys[Math.floor(Math.random() * createdKeys.length)] : 'Pol001:Ins001';
            args = [...key.split(':'), 'Inc001'];
            break;

        default:
            args = ['Pol001', 'Ins001'];
            break;
    }

    return context.invokeChaincode('basic', fcn, args, 'channel1');
};

module.exports.end = async function() {};
