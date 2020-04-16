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
title: CloseAccount
summary: This action deposits tokens into the bank account (and the vault). It
is auto-triggered by eosio.token:transfer.
icon:

<h1 class="contract">withdraw</h1>
---
spec-version: 0.0.1
title: CloseAccount
summary: This action withdraws tokens from the bank account (and the vault).
icon:
