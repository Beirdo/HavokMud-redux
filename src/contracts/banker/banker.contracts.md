<h1 class="contract">newaccount</h1>
---
spec-version: 0.0.1
title: NewAccount
summary: This action will create a new bank account for the user.  If an entry
already exist, no action is taken.  The RAM costs are paid by the user.
icon:

<h1 class="contract">closeaccount</h1>
---
spec-version: 0.0.1
title: CloseAccount
summary: This action removes a bank account belonging to the user.  If no
entry exists, an error is raised.  Before the row is erased, the contents of
the account will be transfered to the user.
icon:

<h1 class="contract">deposit</h1>
---
spec-version: 0.0.1
title: Deposit
summary: This action deposits tokens into the bank account (and the vault). It
is auto-triggered by eosio.token:transfer.
icon:

<h1 class="contract">withdraw</h1>
---
spec-version: 0.0.1
title: Withdraw
summary: This action withdraws tokens from the bank account (and the vault).
icon:

<h1 class="contract">setinterest</h1>
---
spec-version: 0.0.1
title: SetInterest
summary: This action sets the interest rate.  It can only be used by the 
system account.  The interest rate is in units of 100th of %, and is given as
an integer.
icon:

<h1 class="contract">calcinterest</h1>
---
spec-version: 0.0.1
title: CalcInterest
summary: This action calculates and deposits interest for all interest-bearing
bank accounts.  It can only be used by the system account.  All interest
deposits will be done in CP, and this is intended to be run periodically.  The
interest is calculated on a per-annum basis, and is accumulated since the last
time interest was calculated.
icon:

<h1 class="contract">sendreserve</h1>
---
spec-version: 0.0.1
title: SendReserve
summary: This action calculates and transfers coins to/from the system account
to get the vault to an expected overall float amount.  Any excess will be sent
to the system account, and any shortfall will be requested from the system
account.  It can only be used by the system account.
icon:
