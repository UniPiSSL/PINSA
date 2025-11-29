
'use strict';

// Deterministic JSON.stringify()
const stringify  = require('json-stringify-deterministic');
const sortKeysRecursive  = require('sort-keys-recursive');
const { Contract } = require('fabric-contract-api');

class AssetTransfer extends Contract {

    async InitLedger(ctx) {

        const policyholders = [
            {
                PolicyholderID: 'Pol001',
                InsurancecompanyID: 'Ins001',
                Premium: 100000,
                Limit: 10000000,
                Deductible: 10000,
                Risklevel: '',
                Totalmoneyrisk: 0,                
                Reputation: 100,
                Startdate: 20230101,
                Enddate: 20230701,
                Coverages : ['wiretransferfraud','programmingerror', 'staffmistake'],
                Obligations : {
                    penetrationtests: 9, 
                    stafftraining: 9,
                    backup: 9
                },
                Controls : {
                    penetrationtests: 3, 
                    stafftraining: 2,
                    backup: 1
                },
                Incidents:[ 
                    {incidentID:'Inc001', incidentName:'programmingerror', indemnification:1000, status:1, message:''}, 
                    {incidentID:'Inc002', incidentName:'legalaction', indemnification:1000, status:1, message:''}, 
                    {incidentID:'Inc003', incidentName:'ransomware', indemnification:16000, status:2, message:''} ]
            },
            {
                PolicyholderID: 'Pol002',
                InsurancecompanyID: 'Ins002',                
                Premium: 800000,
                Limit: 8000000,
                Deductible: 8000,
                Risklevel: '',
                Totalmoneyrisk: 0,
                Reputation: 100,
                Startdate: 20230101,
                Enddate: 20240101,
                Coverages : ['legalaction','lostdevice', 'hacker'],
                Obligations : {
                    penetrationtests: 8, 
                    stafftraining: 8,
                    backup: 8
                },
                Controls : {
                    penetrationtests: 8, 
                    stafftraining: 8,
                    backup: 8
                },
                Incidents:[] 
            }
        ];

        for (const policyholder of policyholders) {
            let key = policyholder.PolicyholderID + ':' + policyholder.InsurancecompanyID;            
            await ctx.stub.putState(key, Buffer.from(stringify(sortKeysRecursive(policyholder))));            
        }
    }
    
    async PolicyholderExists(ctx, policyholderID, insurancecompanyID) {

        let key = policyholderID + ':' + insurancecompanyID;
        
        const policyholderJSON = await ctx.stub.getState(key);
        return policyholderJSON && policyholderJSON.length > 0;
    }

    async ReadPolicyholder(ctx, policyholderID, insurancecompanyID) {
        
        let key = policyholderID + ':' + insurancecompanyID;
        
        const policyholderJSON = await ctx.stub.getState(key); // get the policyholderJSON from chaincode state
        if (!policyholderJSON || policyholderJSON.length === 0) {
            throw new Error(`The policyholder ${policyholderID} and insurancecompany ${insurancecompanyID} does not exist`);            
        }
        return policyholderJSON.toString();
    }
    
    async GetAllPolicyholders(ctx) {
        const allResults = [];
        // range query with empty string for startKey and endKey does an open-ended query of all policyholders in the chaincode namespace.
        const iterator = await ctx.stub.getStateByRange('', '');
        let result = await iterator.next();
        while (!result.done) {
            const strValue = Buffer.from(result.value.value.toString()).toString('utf8');
            let record;
            try {
                record = JSON.parse(strValue);
            } catch (err) {
                console.log(err);
                record = strValue;
            }
            allResults.push(record);
            result = await iterator.next();
        }
        return JSON.stringify(allResults);
    }

    async DeleteAllPolicyholders(ctx) {

        const iterator = await ctx.stub.getStateByRange('', '');
        let result = await iterator.next();
        while (!result.done) {
            const strValue = Buffer.from(result.value.value.toString()).toString('utf8');
            let record = '';
            try {
                record = JSON.parse(strValue);
            } catch (err) {
                console.log(err);
                record = strValue;
            }
            let key = record.PolicyholderID + ':' + record.InsurancecompanyID;
            await ctx.stub.deleteState(key);        
            result = await iterator.next();
        }
    }

    async CreatePolicyholder(ctx, policyholderID, insurancecompanyID, premium, limit, deductible, startdate, enddate, coverages, obligations, controls) {

        let key = policyholderID + ':' + insurancecompanyID;

        const exists = await this.PolicyholderExists(ctx, policyholderID, insurancecompanyID);

        if (exists) {
            throw new Error(`The policyholder ${policyholderID} and ${insurancecompanyID} already exists`);
        }

        let oblig = {};
        let oblig_names = obligations.split("-")[0].split(",");
        let oblig_counters = obligations.split("-")[1].split(",");

        for (let index = 0; index < oblig_names.length; ++index) {
            oblig[oblig_names[index]] = parseInt(oblig_counters[index]);
        }

        let contr = {};
        let contr_names = controls.split("-")[0].split(",");
        let contr_counters = controls.split("-")[1].split(",");

        for (let index = 0; index < contr_names.length; ++index) {
            contr[contr_names[index]] = parseInt(contr_counters[index]);
        }

        const policyholder = {
            PolicyholderID: policyholderID,
            InsurancecompanyID: insurancecompanyID, 
            Premium: parseInt(premium),
            Limit: parseInt(limit),
            Deductible: parseInt(deductible),        
            Risklevel: '',
            Totalmoneyrisk: 0,            
            Reputation: 100,
            Startdate: parseInt(startdate),
            Enddate: parseInt(enddate),
            Coverages: coverages.split("-"),
            Obligations: oblig,
            Controls: contr,
            Incidents: []
        };

        //we insert data in alphabetic order using 'json-stringify-deterministic' and 'sort-keys-recursive'
        await ctx.stub.putState(key, Buffer.from(stringify(sortKeysRecursive(policyholder))));
        return JSON.stringify(policyholder);
    }
      
    async DeletePolicyholder(ctx, policyholderID, insurancecompanyID) {
        
        let key = policyholderID + ':' + insurancecompanyID;

        const exists = await this.PolicyholderExists(ctx, policyholderID, insurancecompanyID);
        if (!exists) {
            throw new Error(`The policyholder ${policyholderID} and insuraceCompany ${insurancecompanyID} does not exist`);
        }
        return ctx.stub.deleteState(key);
    }

    async UpdatePolicyholder(ctx, policyholderID, insurancecompanyID, risklevel, totalmoneyrisk) {

        let key = policyholderID + ':' + insurancecompanyID;

        const policyholderString = await this.ReadPolicyholder(ctx, policyholderID, insurancecompanyID);
        const policyholder = JSON.parse(policyholderString);
        policyholder.Risklevel = risklevel;
        policyholder.Totalmoneyrisk = parseInt(totalmoneyrisk);        
        return ctx.stub.putState(key, Buffer.from(stringify(sortKeysRecursive(policyholder))));
    }
    
    async GetPolicyholderHistory(ctx, policyholderID, insurancecompanyID) {

        let key = policyholderID + ':' + insurancecompanyID;

        let iterator = await ctx.stub.getHistoryForKey(key);
        let allResults = [];        

        let res = { done: false, value: null };

        while(true) {
            res = await iterator.next();
            let jsonRes = {};

            if (res.value && res.value.value.toString()) {
                jsonRes.TxId = res.value.txId;
                jsonRes.Timestamp = res.value.timestamp;                                
                jsonRes.Value = JSON.parse(res.value.value.toString('utf8'));
                allResults.push(jsonRes);                
            }

            if (res.done) {
                await iterator.close();
                return allResults; 
            }

        }

        return 'Return: ' + ' ' + allResults.toString();
    }

    async AnalyzeContract(ctx, policyholderID, insurancecompanyID) {

        let key = policyholderID + ':' + insurancecompanyID;

        const exists = await this.PolicyholderExists(ctx, policyholderID, insurancecompanyID);

        if (!exists) {            
            throw new Error(`The policyholder ${policyholderID} and insuraceCompany ${insurancecompanyID} does not exist`);
        }

        const policyholderString = await this.ReadPolicyholder(ctx, policyholderID, insurancecompanyID);
        const policyholder = JSON.parse(policyholderString);

        let Coverages = policyholder.Coverages;
        let Obligations = policyholder.Obligations;

        let myRetVal = { Coverages, Obligations };
        return JSON.stringify(myRetVal);
    }

    async CheckObligations(ctx, policyholderID, insurancecompanyID) {

        let key = policyholderID + ':' + insurancecompanyID;

        const exists = await this.PolicyholderExists(ctx, policyholderID, insurancecompanyID);

        if (!exists) {            
            throw new Error(`The policyholder ${policyholderID} and insuraceCompany ${insurancecompanyID} does not exist`);
        }

        const policyholderString = await this.ReadPolicyholder(ctx, policyholderID, insurancecompanyID);
        const policyholder = JSON.parse(policyholderString);

        const controlsKeys = Object.keys(policyholder.Controls);
        const obligationsKeys = Object.keys(policyholder.Obligations);

        if(controlsKeys.length !== obligationsKeys.length) {
            await this.Violate(ctx,policyholderID, insurancecompanyID);
            return false;
        }

        for (let objKey of controlsKeys) {
            if (policyholder.Controls[objKey] !== policyholder.Obligations[objKey]) {
                if(typeof policyholder.Controls[objKey] == "object" && typeof policyholder.Obligations[objKey] == "object") {
                    if(!isEqual(policyholder.Controls[objKey], policyholder.Obligations[objKey])) {
                        await this.Violate(ctx,policyholderID, insurancecompanyID);
                        return false;
                    }
                } 
                else {                    
                    await this.Violate(ctx,policyholderID, insurancecompanyID);
                    return false;
                }
            }
        }

        return true;
    }

    async Violate(ctx, policyholderID, insurancecompanyID) {

        let key = policyholderID + ':' + insurancecompanyID;

        const policyholderString = await this.ReadPolicyholder(ctx, policyholderID, insurancecompanyID);
        const policyholder = JSON.parse(policyholderString);
        policyholder.Reputation = policyholder.Reputation -1;
        await ctx.stub.putState(key, Buffer.from(stringify(sortKeysRecursive(policyholder))));
        return policyholder.Reputation;
    }
    
    async ReportIncident(ctx, p_policyholderID, p_insurancecompanyID, p_incidentID, p_incidentName, p_indemnification) {

        let key = p_policyholderID + ':' + p_insurancecompanyID;

        const policyholderString = await this.ReadPolicyholder(ctx, p_policyholderID, p_insurancecompanyID);
        const policyholder = JSON.parse(policyholderString);
        
        let newIncident = {incidentID:p_incidentID, incidentName:p_incidentName, indemnification:parseInt(p_indemnification), status:2, message:''};
        policyholder.Incidents.push(newIncident);

        return ctx.stub.putState(key, Buffer.from(stringify(sortKeysRecursive(policyholder))));
    }

    async ResponseIncident(ctx, policyholderID, insurancecompanyID, p_incidentID) {

        let key = policyholderID + ':' + insurancecompanyID;

        const policyholderString = await this.ReadPolicyholder(ctx, policyholderID, insurancecompanyID);
        const policyholder = JSON.parse(policyholderString);

        let retMessage = 'Incident not found';
        let changed = false;

        policyholder.Incidents.forEach(incident => {    

            if(incident.incidentID == p_incidentID) {            

                if(incident.status == 1){                    
                    retMessage = 'Incident has already resolved.';
                }

                if(incident.status == 2){
                    let incidentCost = 0;                
                    let incidentName = incident.incidentName;

                    switch(incidentName) {
                        case 'businessemailcompromise':
                            incidentCost = 123000;
                            break;
                        case 'hacker':
                            incidentCost = 430000;
                            break;
                        case 'legalaction':
                            incidentCost = 90000;
                            break;
                        case 'lostdevice':
                            incidentCost = 57000;
                            break;              
                        case 'malware/virus':
                            incidentCost = 160000;
                            break;              
                        case 'negligence':
                            incidentCost = 63000;
                            break;              
                        case 'phishing':
                            incidentCost = 72000;
                            break;              
                        case 'privacybreach':
                            incidentCost = 13000;
                            break;              
                        case 'programmingerror':
                            incidentCost = 348000;
                            break;              
                        case 'ransomware':
                            incidentCost = 179000;
                            break;              
                        case 'rogueemployee/malisiousinsider':
                            incidentCost = 91000;
                            break;      
                        case 'socialengineering':
                            incidentCost = 114000;
                            break;
                        case 'staffmistake':
                            incidentCost = 13000;
                            break;
                        case 'systemglitch':
                            incidentCost = 1500000;
                            break;
                        case 'theftofhardware':
                            incidentCost = 16000;
                            break;
                        case 'theftofmoney':
                            incidentCost = 102000;
                            break;
                        case 'thirdparty':
                            incidentCost = 33000;
                            break;
                        case 'trademark/copyrightinfringement':
                            incidentCost = 166000;
                            break;
                        case 'unauthorizedaccess':
                            incidentCost = 20000;
                            break;
                        case 'wiretransferfraud':
                            incidentCost = 289000;
                            break;
                        case 'wrongfuldatacollection':
                            incidentCost = 42000;
                            break;
                        case 'other':
                            incidentCost = 58000;
                            break;              
                        default:
                            incidentCost = 69000;
                            break;
                    }        

                    let finalIndemnification = 0;

                    if(incident.indemnification > policyholder.Deductible) {
                        finalIndemnification = incident.indemnification - policyholder.Deductible;
                    }
                    else {
                        finalIndemnification = 0;
                    }

                    let message = '';

                    if(finalIndemnification > 0 && finalIndemnification <= policyholder.Limit && finalIndemnification <= incidentCost) {
                        policyholder.Limit = policyholder.Limit - finalIndemnification;
                        message = `Incident resolved. Limit is reduced by ${finalIndemnification}`;
                    }
                    else {
                        message = 'Incident resolved. Limit no changed.';
                    }

                    incident.status = 1;
                    incident.message = message;         
                    retMessage = message;  
                    changed = true;                    
                }

            }

        }); 

        if(changed){
            await ctx.stub.putState(key, Buffer.from(stringify(sortKeysRecursive(policyholder)))); 
        }
        
        return retMessage;
    }  
    
}

module.exports = AssetTransfer;