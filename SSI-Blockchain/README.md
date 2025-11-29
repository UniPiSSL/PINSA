# Commands for Interaction between NCSA, Policyholder and Insurance Company

1. Start ledger
```
cd von-network
sudo ./manage build
sudo ./manage start
```

2. Start NCSA
```
cd aries-cloudagent-python
sudo ./run_demo ncsa
```

3. Start Policyholder
```
cd aries-cloudagent-python
sudo ./run_demo policyholder
```

4. Start Insurace Company
```
cd aries-cloudagent-python
sudo ./run_demo insurancecompany
```

# Commands for Performance

1. Run this statement for 100 cred or 100 pres
```
cd aries-cloudagent-python
sudo ./run_demo performance --count 100
```
