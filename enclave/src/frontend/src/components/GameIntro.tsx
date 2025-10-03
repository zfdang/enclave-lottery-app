import React from 'react'
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, Typography, Box } from '@mui/material'
import { InfoOutlined } from '@mui/icons-material'

type Props = {
  open: boolean
  onClose: () => void
}

export default function GameIntro({ open, onClose }: Props) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box display="flex" alignItems="center">
          <InfoOutlined sx={{ mr: 1 }} />
          Game Introduction
        </Box>
      </DialogTitle>
      <DialogContent dividers sx={{ maxHeight: '70vh' }}>
        <Typography variant="h6" sx={{ mb: 1 }}>1. How to play</Typography>
        <Typography variant="body2" paragraph>
          - Connect your Web3 wallet using the wallet icon. Make sure your wallet is connected to the same network (Base Sepolia Testnet: <a href="https://chainlist.org/chain/84532" target="_blank" rel="noopener noreferrer">https://chainlist.org/chain/84532</a>) the contract is deployed on.
        </Typography>
        <Typography variant="body2" paragraph>
          - Place a bet by entering an amount (must be at least the minimum bet) and submitting. Each bet registers your participation in the current round. You can place multiple bets in a round to increase your chances of winning.
        </Typography>
        <Typography variant="body2" paragraph>
          - When betting closes, the operator (running inside a verified enclave) will trigger a secure drawing of the winner based on on-chain state and the randomness/source agreed in the contract.
        </Typography>

        <Typography variant="h6" sx={{ mb: 1 }}>2. Why the game is safe</Typography>
        <Typography variant="body2" paragraph>
          - Deterministic, on-chain state: All bets and participant lists are stored on-chain in the smart contract. The outcome is determined using values that are verifiable on-chain, preventing tampering with participant lists or bets.
        </Typography>
        <Typography variant="body2" paragraph>
          - Clear rules & transparent payouts: The contract enforces minimum bet, participant eligibility, and payout splits. Payout math is implemented in the contract and cannot be changed without redeploying.
        </Typography>
        <Typography variant="body2" paragraph>
          - You bet to the online contract directly from your wallet. The contract holds the funds and automatically pays out winners or refunds all participants; the operator cannot access player funds.
        </Typography>

        <Typography variant="h6" sx={{ mb: 1 }}>3. Technical safety guarantees</Typography>
        <Typography variant="body2" paragraph>
          - Enclave-backed operator: The off-chain operator that triggers draws and refunds runs inside an AWS Nitro Enclave. The enclave provides hardware-backed isolation and attestation so you can verify the operator is running the approved binary.
        </Typography>
        <Typography variant="body2" paragraph>
          - Auditable actions: Every operator action (draw, refund) is recorded on-chain as a transaction. You can inspect the transaction history on-chain and cross-check it with the UI activity feed.
        </Typography>
        <Typography variant="body2" paragraph>
          - Verifiable randomness (if used): The drawing logic uses on-chain verifiable sources (or a randomness oracle when configured). The exact randomness source and computation are visible in the contract code.
        </Typography>

        <Typography variant="h6" sx={{ mb: 1 }}>4. Notes</Typography>
        <Typography variant="body2" paragraph>
          - For technical users: The whole protocol (smart contract code, off-chain operator binary behavior, and attestation details) is available in the repository: <a href="https://github.com/zfdang/enclave-lottery-app/" target="_blank" rel="noopener noreferrer">https://github.com/zfdang/enclave-lottery-app/</a>. You can verify the attestation document via the "Nitro Enclave Verified" badge.
        </Typography>
        <Typography variant="body2" paragraph>
          - If you suspect a problem, check the backend status indicator. The app surfaces backend health; if the backend is offline, avoid betting until the issue is resolved and you can confirm the operator's status.
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  )
}
