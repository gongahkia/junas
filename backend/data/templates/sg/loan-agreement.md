---
id: loan-agreement-sg
title: Loan Agreement
category: Finance
jurisdiction: Singapore
description: Basic Singapore-governed private loan agreement.
source_urls:
  - https://sso.agc.gov.sg/Act/CLA1909
variables:
  - name: lender
    label: Lender
    placeholder: ABC Pte Ltd
  - name: borrower
    label: Borrower
    placeholder: XYZ Pte Ltd
  - name: principal
    label: Principal
    placeholder: SGD 50,000
  - name: interest
    label: Interest Rate
    placeholder: 5% per annum
  - name: maturity
    label: Maturity Date
    placeholder: 2027-01-01
    type: date
---
# LOAN AGREEMENT

**Parties:** {{lender}} ("Lender") and {{borrower}} ("Borrower").

## 1. LOAN
The Lender agrees to lend {{principal}} to the Borrower.

## 2. INTEREST
Interest accrues at {{interest}}, calculated daily and payable with principal unless otherwise agreed.

## 3. REPAYMENT
The Borrower shall repay all outstanding principal and interest by {{maturity}}.

## 4. PREPAYMENT
The Borrower may prepay the loan in whole or in part without penalty unless the parties agree otherwise in writing.

## 5. DEFAULT
An event of default occurs if the Borrower fails to pay an amount due within 7 days after written notice.

## 6. GOVERNING LAW
This Agreement is governed by the laws of Singapore.

---
This template is for informational purposes only and is not legal advice. See README.md §Disclaimer.
