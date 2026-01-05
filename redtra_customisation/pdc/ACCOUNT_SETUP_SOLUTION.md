# Complete PDC Account Setup Solution

## Problem Summary

1. **"Cannot Update After Submit"** - Cheque Details field cannot be edited after submission
2. **"Party Type and Party is required"** - Journal Entry validation error when account type is Receivable/Payable
3. **Account structure confusion** - What account types and parent accounts to use

## Solution

### Account Configuration

#### 1. PDC Received Account (Customer Cheques)
```
Account Name: PDC Received
Account Type: Current Asset
Parent Account: Current Assets → Trade Receivables (or any Current Asset group)
Is Group: No
Party Required: No
```

#### 2. PDC Issued Account (Supplier Cheques)
```
Account Name: PDC Issued  
Account Type: Current Liability
Parent Account: Current Liabilities → Trade Payables (or any Current Liability group)
Is Group: No
Party Required: No
```

#### 3. Under Collection Account (Recommended: Use Current Asset)
```
Account Name: PDC Under Collection
Account Type: Current Asset (RECOMMENDED - No party required)
Parent Account: Current Assets → Trade Receivables
Is Group: No
Party Required: No

OR (Alternative if you need party tracking):

Account Name: PDC Under Collection - Receivables
Account Type: Receivable
Parent Account: Accounts Receivable
Is Group: No
Party Required: Yes (Customer)
```

### Why Current Asset is Recommended for Under Collection

- **No Party Tracking Required**: Journal Entries don't need party fields
- **Simpler Setup**: One account for both customer and supplier cheques
- **Works with PDF Reports**: No party validation errors
- **Flexible**: Can track amounts without party dependency

### Complete Chart of Accounts Structure

```
Assets (Root)
  └── Current Assets
      ├── Trade Receivables
      │   ├── Accounts Receivable (Account Type: Receivable)
      │   ├── PDC Received (Account Type: Current Asset) ⭐
      │   └── PDC Under Collection (Account Type: Current Asset) ⭐
      └── Bank Accounts
          └── [Your Bank Accounts]

Liabilities (Root)
  └── Current Liabilities
      └── Trade Payables
          ├── Accounts Payable (Account Type: Payable)
          └── PDC Issued (Account Type: Current Liability) ⭐
```

### Step-by-Step Setup

1. **Create PDC Received Account**
   - Go to Chart of Accounts
   - Click "New Account"
   - Account Name: `PDC Received`
   - Parent Account: Select "Current Assets" → "Trade Receivables" (or create if doesn't exist)
   - Account Type: `Current Asset`
   - Save

2. **Create PDC Issued Account**
   - Account Name: `PDC Issued`
   - Parent Account: Select "Current Liabilities" → "Trade Payables" (or create if doesn't exist)
   - Account Type: `Current Liability`
   - Save

3. **Create Under Collection Account**
   - Account Name: `PDC Under Collection`
   - Parent Account: Select "Current Assets" → "Trade Receivables"
   - Account Type: `Current Asset` ⚠️ **NOT Receivable or Payable**
   - Save

4. **Configure in PDC Settings**
   - Go to PDC Settings
   - Select the three accounts you created
   - Save

### Code Fixes Applied

✅ **Fixed "Cannot Update After Submit"**
- Added `allow_on_submit: 1` to pdc_cheque_details field
- Status field now allows updates after submit (controlled by workflow buttons)

✅ **Fixed "Party Required" Error**
- Code now checks account type before adding party fields
- Party fields only added if account type is "Receivable" or "Payable"
- Works with Current Asset accounts (no party required)

### Testing Checklist

- [ ] Create all three accounts with correct types
- [ ] Configure accounts in PDC Settings
- [ ] Create Payment Entry with cheque
- [ ] Submit Payment Entry
- [ ] Mark as "Under Collection" - should create JE without errors
- [ ] Mark as "Collected" - should create JE without errors
- [ ] Check that Cheque Details table can be updated after submit
- [ ] Verify PDF export works

### Common Errors and Fixes

**Error**: "Party Type and Party is required for Receivable / Payable account"
**Fix**: Change Under Collection account type to "Current Asset" instead of "Receivable" or "Payable"

**Error**: "Cannot Update After Submit"
**Fix**: Code updated to allow Cheque Details updates. Ensure custom fields are migrated: `bench migrate`

**Error**: Account not found in filters
**Fix**: Ensure accounts are created in the correct company and configured in PDC Settings

