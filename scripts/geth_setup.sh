#!/bin/bash
set -e

DATADIR="$HOME/geth-runtime"

# Clean up any existing data directory
rm -rf "$DATADIR"
mkdir -p "$DATADIR"

echo "==> generate genesis.json (20 wallets as Anvil)..."

cat > genesis.json <<EOF
{
  "config": {
    "chainId": 31337,
    "homesteadBlock": 0,
    "eip150Block": 0,
    "eip155Block": 0,
    "eip158Block": 0,
    "byzantiumBlock": 0,
    "constantinopleBlock": 0,
    "petersburgBlock": 0,
    "istanbulBlock": 0
  },
  "alloc": {
    "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266": { "balance": "0x3635C9ADC5DEA00000" },
    "0x70997970C51812dc3A010C7d01b50e0d17dc79C8": { "balance": "0x3635C9ADC5DEA00000" },
    "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC": { "balance": "0x3635C9ADC5DEA00000" },
    "0x90F79bf6EB2c4f870365E785982E1f101E93b906": { "balance": "0x3635C9ADC5DEA00000" },
    "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65": { "balance": "0x3635C9ADC5DEA00000" },
    "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc": { "balance": "0x3635C9ADC5DEA00000" },
    "0x976EA74026E726554dB657fA54763abd0C3a0aa9": { "balance": "0x3635C9ADC5DEA00000" },
    "0x14dC79964da2C08b23698B3D3cc7Ca32193d9955": { "balance": "0x3635C9ADC5DEA00000" },
    "0x23618e81E3f5c7a7c57C6e27f85EcaCE1d64cE71": { "balance": "0x3635C9ADC5DEA00000" },
    "0xa0Ee7A142d267C1f36714E4a8F75612F20a79720": { "balance": "0x3635C9ADC5DEA00000" },
    "0xBcd4042DE499D14e55001CcbB24a551F3b954096": { "balance": "0x3635C9ADC5DEA00000" },
    "0x71bE63f3384f5fb98995898A86B02Fb2426c5788": { "balance": "0x3635C9ADC5DEA00000" },
    "0xFABB0ac9d68B0B445fB7357272Ff202C5651694a": { "balance": "0x3635C9ADC5DEA00000" },
    "0x1CBd3b2770909D4e10f157cABC84C7264073C9Ec": { "balance": "0x3635C9ADC5DEA00000" },
    "0xdF3e18d64BC6A983f673Ab319CCaE4f1a57C7097": { "balance": "0x3635C9ADC5DEA00000" },
    "0xcd3B766CCDd6AE721141F452C550Ca635964ce71": { "balance": "0x3635C9ADC5DEA00000" },
    "0x2546BcD3c84621e976D8185a91A922aE77ECEc30": { "balance": "0x3635C9ADC5DEA00000" },
    "0xbDA5747bFD65F08deb54cb465eB87D40e51B197E": { "balance": "0x3635C9ADC5DEA00000" },
    "0xdD2FD4581271e230360230F9337D5c0430Bf44C0": { "balance": "0x3635C9ADC5DEA00000" },
    "0x8626f6940E2eb28930eFb4CeF49B2d1F2C9C1199": { "balance": "0x3635C9ADC5DEA00000" }
  },
  "difficulty": "1",
  "gasLimit": "0x47E7C4"
}
EOF


# Install geth if not already installed (Amazon Linux 2023)
 if ! which geth > /dev/null 2>&1; then
  echo "geth not found, installing..."
   # Install geth via tar.gz (use a legacy-compatible 1.13.x release by default)
   : ${GETH_VERSION:=1.11.6}
   echo "Using geth version: $GETH_VERSION"
   GETH_TGZ_URL="https://gethstore.blob.core.windows.net/builds/geth-linux-amd64-1.11.6-ea9e62ca.tar.gz"
   TMP_TGZ="/tmp/geth-${GETH_VERSION}.tar.gz"

  echo "Downloading geth tarball..."
  if curl -fSL "$GETH_TGZ_URL" -o "$TMP_TGZ"; then
    echo "Downloaded tarball, extracting and installing binary..."
    tar -xzf "$TMP_TGZ" -C /tmp
    EXDIR=$(tar -tzf "$TMP_TGZ" | head -1 | cut -f1 -d"/")
    if [ -x "/tmp/${EXDIR}/geth" ]; then
      sudo cp "/tmp/${EXDIR}/geth" /usr/local/bin/geth
      sudo chmod +x /usr/local/bin/geth
      echo "geth binary installed to /usr/local/bin/geth"
    else
      echo "geth binary not found in extracted tarball, aborting." >&2
      rm -rf "/tmp/${EXDIR}" "$TMP_TGZ"
      exit 1
    fi
    rm -rf "/tmp/${EXDIR}" "$TMP_TGZ"
  else
     echo "Failed to download geth tarball for version $GETH_VERSION; please install geth manually or set GETH_VERSION to a valid 1.13.x release." >&2
    exit 1
  fi
else
  echo "geth already installed, skipping installation."
fi


echo "==> initialize chain..."
geth --datadir "$DATADIR" init genesis.json

echo "==> start Geth (background)..."
# start geth in background, capture logs and pid
nohup geth --datadir "$DATADIR" \
     --networkid 31337 \
     --http --http.addr 0.0.0.0 --http.port 8545 \
     --http.api eth,net,web3,personal,miner \
     --allow-insecure-unlock \
     --nodiscover > "$DATADIR/geth.log" 2>&1 &

echo $! > "$DATADIR/geth.pid"
echo "geth started (pid $(cat \"$DATADIR/geth.pid\")). Logs: $DATADIR/geth.log"

echo "Waiting for HTTP RPC at http://127.0.0.1:8545 ..."
for i in {1..20}; do
  if curl -sS --fail http://127.0.0.1:8545 >/dev/null 2>&1; then
    echo "HTTP RPC is up"
    break
  fi
  sleep 1
done
if ! curl -sS --fail http://127.0.0.1:8545 >/dev/null 2>&1; then
  echo "Warning: HTTP RPC did not come up within timeout. Check $DATADIR/geth.log for details." >&2
fi


echo
echo "==> 10 pre-funded accounts and private keys (Anvil/Hardhat defaults):"

cat <<'ACCOUNTS'
1
0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
------
2
0x70997970C51812dc3A010C7d01b50e0d17dc79C8
0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d
------
3
0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC
0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a
------
4
0x90F79bf6EB2c4f870365E785982E1f101E93b906
0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6
------
5
0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65
0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a
------
6
0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc
0x8b3a350cf5c34c9194ca85829a2df0ec3153be0318b5e2d3348e872092edffba
------
7
0x976EA74026E726554dB657fA54763abd0C3a0aa9
0x92db14e403b83dfe3df233f83dfa3a0d7096f21ca9b0d6d6b8d88b2b4ec1564e
------
8
0x14dC79964da2C08b23698B3D3cc7Ca32193d9955
0x4bbbf85ce3377467afe5d46f804f221813b2bb87f24d81f60f1fcdbf7cbf4356
------
9
0x23618e81E3f5c7a7c57C6e27f85EcaCE1d64cE71
0xdbda1821b80551c9d65939329250298aa3472ba22feea921c0cf5d620ea67b97
------
10
0xa0Ee7A142d267C1f36714E4a8F75612F20a79720
0x2a871d0798f97d79848a013d4936a73bf4cc922c825d33c1cf7073dff6d409c6
------
11
0xBcd4042DE499D14e55001CcbB24a551F3b954096
0xf214f2b2cd398c806f84e317254e0f0b801d0643303237d97a22a48e01628897
------
12
0x71bE63f3384f5fb98995898A86B02Fb2426c5788
0x701b615bbdfb9de65240bc28bd21bbc0d996645a3dd57e7b12bc2bdf6f192c82
------
13
0xFABB0ac9d68B0B445fB7357272Ff202C5651694a
0xa267530f49f8280200edf313ee7af6b827f2a8bce2897751d06a843f644967b1
------
14
0x1CBd3b2770909D4e10f157cABC84C7264073C9Ec
0x47c99abed3324a2707c28affff1267e45918ec8c3f20b8aa892e8b065d2942dd
------
15
0xdF3e18d64BC6A983f673Ab319CCaE4f1a57C7097
0xc526ee95bf44d8fc405a158bb884d9d1238d99f0612e9f33d006bb0789009aaa
------
16
0xcd3B766CCDd6AE721141F452C550Ca635964ce71
0x8166f546bab6da521a8369cab06c5d2b9e46670292d85c875ee9ec20e84ffb61
------
17
0x2546BcD3c84621e976D8185a91A922aE77ECEc30
0x689af8efa8c651a91ad287602527f3af2fe9f6501a7ac4b061667b5a93e037fd
------
18
0xbDA5747bFD65F08deb54cb465eB87D40e51B197E
0xde9be858da4a475276426320d5e9262ecfc3ba460bfac56360bfa6c4c28b4ee0
------
19
0xdD2FD4581271e230360230F9337D5c0430Bf44C0
0xdf57089febbacf7ba0bc227dafbffa9fc08a93fdc68e1e42411a14efcf23656e
------
20
0x8626f6940E2eb28930eFb4CeF49B2d1F2C9C1199
0x0df57089febbacf7ba0bc227dafbffa9fc08a93fdc68e1e42411a14efcf23656e
ACCOUNTS

echo
echo "WARNING: These private keys are for local development only. Do NOT use them on mainnet!"
