# PDC Account Setup Guide

## Account Structure for PDC Management

### 1. PDC Received Account (for Customer Cheques)
- **Account Name**: PDC Received
- **Account Type**: Current Asset
- **Parent Account**: Current Assets (or a sub-group like "Trade Receivables" or "Bank Accounts")
- **Is Group**: No
- **Party Type**: Not required
- **Why**: This account holds cheques received from customers before deposit. It's an asset but doesn't need party tracking at this stage.

### 2. PDC Issued Account (for Supplier Cheques)  
- **Account Name**: PDC Issued
- **Account Type**: Current Liability
- **Parent Account**: Current Liabilities (or a sub-group like "Trade Payables")
- **Is Group**: No
- **Party Type**: Not required
- **Why**: This account holds cheques issued to suppliers before clearing. It's a liability but doesn't need party tracking at this stage.

### 3. Under Collection Account
- **Account Name**: PDC Under Collection (or Cheques Under Collection)
- **Account Type**: Receivable (for customer tracking) OR Current Asset
- **Parent Account**: 
  - If Receivable: Accounts Receivable
  - If Current Asset: Current Assets → Trade Receivables
- **Is Group**: No
- **Party Type**: Required only if Account Type = Receivable
- **Why**: This tracks cheques that are deposited but not yet cleared. If using Receivable type, party tracking is enabled.

### Recommended Approach: Use Two Separate Accounts

**Option 1: Separate Accounts (Recommended)**
- **PDC Under Collection - Receivables**: Account Type = Receivable, Parent = Accounts Receivable (for customer cheques)
- **PDC Under Collection - Payables**: Account Type = Payable, Parent = Accounts Payable (for supplier cheques)

**Option 2: Single Current Asset Account**
- Use Account Type = "Current Asset" and handle party tracking differently
- Parent = Current Assets → Trade Receivables (or similar)

## Chart of Accounts Structure Example

```
Assets (Root)
  └── Current Assets
      ├── Accounts Receivable
      │   └── PDC Under Collection - Receivables (Account Type: Receivable)
      └── Trade Receivables
          └── PDC Received (Account Type: Current Asset)

Liabilities (Root)
  └── Current Liabilities
      ├── Accounts Payable
      │   └── PDC Under Collection - Payables (Account Type: Payable)
      └── Trade Payables
          └── PDC Issued (Account Type: Current Liability)
```

## Quick Setup Steps

1. Go to **Chart of Accounts**
2. Create accounts as per the structure above
3. Configure them in **PDC Settings**
4. Ensure Party Type is set only for Receivable/Payable type accounts

