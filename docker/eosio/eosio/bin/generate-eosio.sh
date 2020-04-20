#! /usr/bin/env bash

set -e

BASE_DIR=$(
  cd $(dirname $0)/..
  pwd
)

source ${BASE_DIR}/bin/common_settings.sh

mkdir -p ${KEY_DIR}

# 0. Startup keosd
source ${BASE_DIR}/bin/keosd_start.sh

# 1. Create development wallet
${CLEOS} wallet create -n development -f ${KEY_DIR}/development.password
DEVELOPMENT_PASSWORD=$(cat ${KEY_DIR}/development.password)

# 2. Open the wallet
${CLEOS} wallet open -n development

# 3. Unlock the wallet
${CLEOS} wallet unlock -n development --password ${DEVELOPMENT_PASSWORD}

# 4. Create 2 keys in the wallet, one for development, one as the EOSIO key
${CLEOS} wallet create_key -n development >${KEY_DIR}/development.pubkey
DEVELOPMENT_PUBKEY=$(cat ${KEY_DIR}/development.pubkey | sed -e 's/.*\"\(.*\)\".*/\1/')

${CLEOS} wallet create_key -n development >${KEY_DIR}/eosio.pubkey
EOSIO_PUBKEY=$(cat ${KEY_DIR}/eosio.pubkey | sed -e 's/.*\"\(.*\)\".*/\1/')

# 5. Extract the key pairs
${CLEOS} wallet private_keys -n development --password ${DEVELOPMENT_PASSWORD} >${KEY_DIR}/development_keys.json

# 6. Extract the EOSIO privkey (could use jq, but it's hurting my brain!)
EOSIO_PRIVKEY=$(${BASE_DIR}/bin/extract_private_key.py ${KEY_DIR}/development_keys.json ${EOSIO_PUBKEY})

# 7. Generate the genesis.json file with the new EOSIO key
cat ${BASE_DIR}/genesis/genesis.json.in | sed -e "s/@EOSIO_PUBKEY@/${EOSIO_PASSWORD}/" \
  >${BASE_DIR}/genesis/genesis.json

# 8. Start the genesis producer
bash ${BASE_DIR}/bin/nodeos_start.sh eosio ${EOSIO_PUBKEY} ${EOSIO_PRIVKEY} 8000 9010 genesis

# 9. Shut down the genesis producer
sleep 10
source ${BASE_DIR}/bin/nodeos_stop.sh eosio

# 10.  Start it back up in non-genesis mode
bash ${BASE_DIR}/bin/nodeos_start.sh eosio ${EOSIO_PUBKEY} ${EOSIO_PRIVKEY} 8000 9010

# 11. Create the important system accounts and the base MUD accounts
SYSTEM_ACCOUNTS="eosio.bpay eosio.msig eosio.names eosio.ram eosio.ramfee "
SYSTEM_ACCOUNTS+="eosio.saving eosio.stake eosio.token eosio.vpay eosio.rex "
MUD_ACCOUNTS="mud.havokmud banker"

for account in ${SYSTEM_ACCOUNTS} ${MUD_ACCOUNTS} ; do
  ${CLEOS} wallet create_key -n development > ${KEY_DIR}/${account}.pubkey
  pubkeyname="ACCOUNT_${account/./_}_PUBKEY"
  privkeyname="ACCOUNT_${account/./_}_PRIVKEY"
  ${pubkeyname}=$(cat ${KEY_DIR}/${account}.pubkey | sed -e 's/.*\"\(.*\)\".*/\1/')
  ${CLEOS} wallet private_keys -n development --password ${DEVELOPMENT_PASSWORD} > ${KEY_DIR}/development_keys.json
  ${privkeyname}=$(${BASE_DIR}/bin/extract_private_key.py ${KEY_DIR}/development_keys.json ${${pubkeyname}})
  ${CLEOS} create account eosio ${account} ${DEVELOPMENT_PUBKEY} ${{pubkeyname}}
done

# 12. Install some contracts
EOSIO_OLD_CONTRACTS_DIRECTORY=~/src/eosio.contracts-1.8.x/build/contracts
EOSIO_CONTRACTS_DIRECTORY=~/src/eosio.contracts-1.9.x/build/contracts
HAVOKMUD_CONTRACTS_DIRECTORY=~/src/HavokMud-contracts

${CLEOS} set contract eosio.token ${EOSIO_CONTRACTS_DIRECTORY}/eosio.token/
${CLEOS} set contract eosio.msig ${EOSIO_CONTRACTS_DIRECTORY}/eosio.msig/
${CLEOS} set contract banker ${HAVOKMUD_CONTRACTS_DIRECTORY}/banker/

# 13. Create tokens!
TOKEN_QUANTITY="1000000000.0000"  # 1 billion
MUD_TOKENS="PP GP EP SP CP"
${CLEOS} push action eosio.token create \
  '[ "eosio", "'${TOKEN_QUANTITY}' SYS" ]' \
  -p eosio.token@active
for token in ${MUD_TOKENS} ; do
  ${CLEOS} push action eosio.token create \
    '[ "mud.havokmud", "'"${TOKEN_QUANTITY} ${token}"'" ]' \
    -p eosio.token@active
done

# 14. Issue the tokens!
${CLEOS} push action eosio.token issue \
  '[ "eosio", "'${TOKEN_QUANTITY}'", "Initial Issue" ]' \
  -p eosio.token@active
for token in ${MUD_TOKENS} ; do
  ${CLEOS} push action eosio.token issue \
    '[ "mud.havokmud", "'"${TOKEN_QUANTITY} ${token}"'", "Initial Issue" ]' \
    -p eosio.token@active
done

# 15. Activate PREACTIVATE_FEATURE
curl -X POST http://127.0.0.1:8000 \
  /v1/producer/schedule_protocol_feature_activations \
  -d '{"protocol_features_to_activate": ["0ec7e080177b2c02b278d5088611686b49d739925a92d9bfcacd7fc6b74053bd"]}'

# 16. Setup the eosio.system contract with the old version
${CLEOS} set contract eosio ${EOSIO_OLD_CONTRACTS_DIRECTORY}/eosio.system/

# 17. Turn on a pile of recommended features
# GET_SENDER
${CLEOS} push action eosio activate '["f0af56d2c5a48d60a4a5b5c903edfb7db3a736a94ed589d0b797df33ff9d3e1d"]' -p eosio
# FORWARD_SETCODE
${CLEOS} push action eosio activate '["2652f5f96006294109b3dd0bbde63693f55324af452b799ee137a81a905eed25"]' -p eosio
# ONLY_BILL_FIRST_AUTHORIZER
${CLEOS} push action eosio activate '["8ba52fe7a3956c5cd3a656a3174b931d3bb2abb45578befc59f283ecd816a405"]' -p eosio
# RESTRICT_ACTION_TO_SELF
${CLEOS} push action eosio activate '["ad9e3d8f650687709fd68f4b90b41f7d825a365b02c23a636cef88ac2ac00c43"]' -p eosio@active
# DISALLOW_EMPTY_PRODUCER_SCHEDULE
${CLEOS} push action eosio activate '["68dcaa34c0517d19666e6b33add67351d8c5f69e999ca1e37931bc410a297428"]' -p eosio@active
# FIX_LINKAUTH_RESTRICTION
${CLEOS} push action eosio activate '["e0fb64b1085cc5538970158d05a009c24e276fb94e1a0bf6a528b48fbc4ff526"]' -p eosio@active
# REPLACE_DEFERRED
${CLEOS} push action eosio activate '["ef43112c6543b88db2283a2e077278c315ae2c84719a8b25f25cc88565fbea99"]' -p eosio@active
# NO_DUPLICATE_DEFERRED_ID
${CLEOS} push action eosio activate '["4a90c00d55454dc5b059055ca213579c6ea856967712a56017487886a4d4cc0f"]' -p eosio@active
# ONLY_LINK_TO_EXISTING_PERMISSION
${CLEOS} push action eosio activate '["1a99a59d87e06e09ec5b028a9cbb7749b4a5ad8819004365d02dc4379a8b7241"]' -p eosio@active
# RAM_RESTRICTIONS
${CLEOS} push action eosio activate '["4e7bf348da00a945489b2a681749eb56f5de00b900014e137ddae39f48f69d67"]' -p eosio@active
# WEBAUTHN_KEY
${CLEOS} push action eosio activate '["4fca8bd82bbd181e714e283f83e1b45d95ca5af40fb89ad3977b653c448f78c2"]' -p eosio@active
# WTMSIG_BLOCK_SIGNATURES
${CLEOS} push action eosio activate '["299dcb6af692324b899b39f16d5a530a33062804e41f09dc97e9f156b4476707"]' -p eosio@active

# 18. Update the eosio.system contract
${CLEOS} set contract eosio ${EOSIO_CONTRACTS_DIRECTORY}/eosio.system/

# 19. Make the eosio.msig a privileged account
${CLEOS} push action eosio setpriv '["eosio.msig", 1]' -p eosio@active

# 20. Initialize the system token
${CLEOS} push action eosio init '["0", "4,SYS"]' -p eosio@active

# 21. Create the other three local producer accounts
PRODUCER_ACCOUNTS="prod.1.1 prod.1.2 prod.1.3"

for account in ${PRODUCER_ACCOUNTS} ; do
  ${CLEOS} wallet create_key -n development > ${KEY_DIR}/${account}.pubkey
  pubkeyname="PRODUCER_${account/./_}_PUBKEY"
  privkeyname="PRODUCER_${account/./_}_PRIVKEY"
  ${pubkeyname}=$(cat ${KEY_DIR}/${account}.pubkey | sed -e 's/.*\"\(.*\)\".*/\1/')
  ${CLEOS} wallet private_keys -n development --password ${DEVELOPMENT_PASSWORD} > ${KEY_DIR}/development_keys.json
  ${privkeyname}=$(${BASE_DIR}/bin/extract_private_key.py ${KEY_DIR}/development_keys.json ${${pubkeyname}})
  ${CLEOS} create account eosio --transfer ${account} ${DEVELOPMENT_PUBKEY} ${{pubkeyname}} \
    --stake-net "100000000.0000 SYS" --stake-cpu "100000000.0000 SYS" --buy-ram-kbytes 8192
  rpc_port=${account/prod.1./800}
  p2p_port=${account/prod.1./901}
  ${CLEOS} system regproducer ${account} ${${pubkeyname}}
  # Now do genesis on the new producer
  bash ${BASE_DIR}/bin/nodeos_start.sh ${account} ${${pubkeyname}} ${${privkeyname}} ${rpc_port} ${p2p_port} genesis
  sleep 5
  bash ${BASE_DIR}/bin/nodeos_stop.sh ${account}
  sleep 5
  # And start it up for real
  bash ${BASE_DIR}/bin/nodeos_start.sh ${account} ${${pubkeyname}} ${${privkeyname}} ${rpc_port} ${p2p_port}
done

# 22. Vote for the new producers
${CLEOS} system voteproducer prods ${PRODUCER_ACCOUNTS}

# 23. Resign all the system accounts - not sure I wanna do this...
exit 0

${CLEOS} push action eosio updateauth '{"account": "eosio", "permission": "owner", "parent": "", "auth": {"threshold": 1, "keys": [], "waits": [], "accounts": [{"weight": 1, "permission": {"actor": "eosio.prods", "permission": "active"}}]}}' \
  -p eosio@owner
${CLEOS} push action eosio updateauth '{"account": "eosio", "permission": "active", "parent": "owner", "auth": {"threshold": 1, "keys": [], "waits": [], "accounts": [{"weight": 1, "permission": {"actor": "eosio.prods", "permission": "active"}}]}}' \
  -p eosio@active

for account in ${SYSTEM_ACCOUNTS} ; do
  ${CLEOS} push action eosio updateauth '{"account": "'${account}'", "permission": "owner", "parent": "", "auth": {"threshold": 1, "keys": [], "waits": [], "accounts": [{"weight": 1, "permission": {"actor": "eosio", "permission": "active"}}]}}' \
    -p ${account}@owner
  ${CLEOS} push action eosio updateauth '{"account": "'${account}'", "permission": "active", "parent": "owner", "auth": {"threshold": 1, "keys": [], "waits": [], "accounts": [{"weight": 1, "permission": {"actor": "eosio", "permission": "active"}}]}}' \
    -p ${account}@active
done