# Olmenta user guide

Olmenta helps you give every euro a job. You don't need to know anything about budgeting: the app does the math, and you make the decisions. This guide walks through the app in the order you'll use it.

For debts (cards, loans, money you owe people), see the [debt guide](debt-guide.md).

## The idea in one minute

Olmenta follows one simple method: **budget only the money you already have, and give every euro a job.**

1. **Money arrives.** Your salary or any other income lands in your account. It goes to **Ready to assign**.
2. **You give it jobs.** You split that money across categories: rent, groceries, the car insurance due in March, savings.
3. **You spend from the categories.** Each expense comes out of its category. You can always see how much is left in each one.
4. **Leftovers stay.** Money you don't spend in a category stays there next month. Money you didn't assign also carries over.

Three rules make it work:

- **Only money that has arrived is assigned.** Your next salary isn't in the budget until it lands. Olmenta still plans with it (see [Income](#income)), but it never spends it before it exists.
- **Big yearly bills become small monthly amounts.** A 600 € insurance due in June costs you 50 € every month, so June never hurts.
- **When you overspend, you cover it.** If groceries go over, you move money from another category. Nothing breaks; you just decide where it comes from.

## Getting started

### The setup chat

The first time you open Olmenta, a short chat asks about your life: who you manage money with, where your income comes from, your bank accounts and cards, your home, your car, your subscriptions and your debts. It takes about two minutes, and you can answer by tapping.

At the end you see a **review screen** with everything it proposes: your accounts, your income, your categories, and the people and businesses you pay. Nothing is saved yet. Uncheck what you don't need, rename anything, add what's missing, then confirm.

You can come back to the setup chat any time at `/onboarding`.

### Accounts

**Accounts** (in the sidebar) lists where your money sits:

- **Cash** and **bank accounts** hold your money.
- **Cards** hold debt. A card shows "You owe X €", not a red negative number.

**Add account** creates one. Give it its current balance when you create it, so the app starts from the real amount. For a card, you can also say which day of the month it's charged to your bank.

Every card gets its own payment category in the budget ("Pago Visa BBVA"). That's where the money to pay the card is set aside (see [Credit cards](#credit-cards)).

You can't delete an account, but you can **archive** it: it disappears from the pickers, and its history stays.

## Every day

### Adding a transaction

Recording an expense takes less than five seconds. Tap the **+** button (on mobile, the violet button in the middle of the bottom bar):

1. Type the amount.
2. Pick the category. When you type who you paid, Olmenta remembers the category you used last time.
3. Save. The date is today unless you change it.

Switch to **Income** for money coming in. Income usually has no category: it goes to Ready to assign. An income with a category is a **refund**: it puts money back into that category instead of counting as income.

If you have more than one account, you can also record a **transfer** between them. Transfers are never income or spending; they just move money from one account to another. Paying your card from your bank is a transfer.

### Importing your bank statement

Instead of typing every expense, you can import your bank's statement (BBVA and Sabadell are supported):

1. In **Transactions**, open **Import bank transactions**.
2. Choose the bank, the account it goes into, and the file you downloaded from your bank.
3. Olmenta suggests a category for each row, and a cleaner name for who you paid.
4. **Review your import**: change any category, add a note, mark a row as a transfer between your own accounts, then **Confirm import**.

Rows you've already imported are skipped automatically, so importing the same file twice is safe.

### Transactions without a category

Expenses without a category lower your Ready to assign without saying where the money went. When you have some, the budget shows an **Uncategorized spending** block and the transactions screen offers **Review uncategorized**. The review lists them all; pick a category for each (Olmenta suggests one) and **Apply changes**.

## The budget

**Budgets** is where you give your money its jobs.

### Ready to assign

The big number at the top is the money that doesn't have a job yet. Your goal is to bring it to zero by assigning it to categories. Tap it to see where it comes from: each income of the month, what carried over from last month, and what's already assigned.

### Assigning money

Each category row shows what you assigned, what you spent and what's available. Tap a category to set how much it gets this month. For day-to-day categories (groceries, restaurants, fuel), Olmenta suggests an amount based on last month.

### Categories with payments

Some costs have dates: rent every month, school fees from September to June, insurance once a year. For those, open the category and choose **Set up payments**. Describe each payment once:

- how often it's paid (every month, some months, once a year, every N months, once on a date);
- the amount;
- the day of the month (optional);
- whether the amount varies (water and electricity bills).

Olmenta then works out the monthly amount for you. School fees of 632 € from September to June become 526,67 € every month, July and August included. You never type that number: the category is assigned it automatically.

If you started late and what's saved isn't enough for a payment that's coming, Olmenta shows a higher amount to **be on time**. It drops back to normal once you catch up.

### Moving money

Plans change. **Move money** takes money from one category (or from Ready to assign) and puts it in another. It's how you cover an overspent category, or fund something you forgot.

### When a category goes over

If you spend more than a category has, it shows as overspent and Olmenta offers to cover it from another category in one tap. You're never blocked from recording an expense. If the month closes without covering it, the amount comes out of next month's Ready to assign, and the category starts clean.

### Savings categories

Mark a category as **savings** (emergency fund, a trip, the kids' savings) and its money shows as "saved for the future" instead of "left to spend". Nothing else changes; it's a label that keeps the picture honest.

## This month: the home screen

The home screen answers three questions:

- **What do I have to solve this month?**
  - **Already paid this month** lists the payments that already went out.
  - **Still to pay this month** lists what's coming, with a "covered" or "short X €" tag on each.
  - **Left to spend** is what remains in your day-to-day categories.
- **Where's the rest of my money?** **Saved for the future** and **Unassigned**.
- **Will the next months be covered?** A preview of the next three months, with a link to Upcoming payments.

At the bottom of the side column, a check line shows that it all adds up: the money in your accounts equals what's to pay, plus what's left to spend, plus what's saved, plus what's unassigned.

When something needs your attention, a coach note appears at the top: an income that hasn't arrived, or a debt payment that's late.

## Income

Olmenta needs to know what income you expect, so it can tell you whether your plan fits. Expected income never goes into Ready to assign; only money that actually arrives does.

### Telling Olmenta what you expect

In **Settings → Income** (or **Edit income** in Upcoming payments), add each fixed income once:

- a name ("Nómina", "Pensión", "Alquiler piso");
- the net amount, what actually lands in your account;
- how often it comes, and around which day;
- who pays it (your company, the tenant).

If you get **14 payments a year** (extra pays in June and December), enter your monthly salary and tap **14 payments a year**: Olmenta adds the two extra pays for you.

Bonuses that depend on targets are not fixed income. Don't add them; when one arrives, you assign it like any other money.

### Expected versus received

Tap Ready to assign in the budget to see, for the month:

- each expected income with its status:
  - **received**, with "X € less" or "X € more" when the amount differs;
  - **expected day N**;
  - **not arrived yet**, when it's more than 3 days late;
  - **didn't arrive**, for past months;
- **unplanned income**: money that arrived but didn't match anything you expected.

Olmenta matches incomes by who paid them, or by amount when there's no payer. If it didn't recognize one, use **This is…** on the unplanned income to say which expected income it was. It remembers the payer for the next months.

When an income is late, the home screen shows a coach note with **Add it** (if it arrived and you didn't record it) or **It's already here** (to link it).

## Upcoming payments and the year ahead

**Upcoming** shows the next 12 months if you keep your current plan:

- **Expected income, next 12 months.**
- **Planned costs**, split into payments, day-to-day and goals.
- **The gap**: what's left over or what's missing, per year and per month. If it's short, the plan needs adjusting, and it's better to know now than in March.

Below, each month has a row with its expected income, its payments, a "payments covered" or "short X €" tag, and two bars: how much of your day-to-day budget is funded, and how much is being set aside for later payments. Open a month to see every payment.

Each month's money goes first to that month's payments, then to day-to-day, then to setting aside for later payments and goals. So a short month shows up here months ahead.

## Credit cards

Olmenta handles cards so that paying them never surprises you:

- **A card purchase is spending at the moment you buy.** Groceries paid with the card come out of Groceries straight away, like cash.
- **The money moves to the card's payment category.** When the purchase was budgeted, that amount moves automatically to "Pago (your card)", ready for when the card is charged.
- **Paying the card is a transfer**, from your bank to the card. It doesn't count as spending again.
- **Spending more than a category has, on a card, becomes card debt.** It's not covered by the payment category and shows on the card as "X € not covered".

If your card already carried a balance when you started, that old balance is a debt. The [debt guide](debt-guide.md) explains how to give it a plan.

## Settings

- **Income**: your expected incomes (see [Income](#income)).
- **Categories**: create, rename, group and archive categories. Archived categories keep their history.
- **Accounts & cards**: a shortcut to Accounts.

## Plain-word glossary

- **Ready to assign**: money that has arrived and doesn't have a job yet.
- **Assigned**: what you gave a category this month.
- **Available**: what's left in a category to spend.
- **Carried over**: what stays in a category, or in Ready to assign, from last month.
- **Payment**: a cost with a date (rent, school, insurance), described once with its rule.
- **To be on time**: the monthly amount that catches you up when you're behind on a payment that's coming.
- **Covered / short**: whether the money set aside is enough for a payment.
- **Refund**: money back from a purchase. It returns to the purchase's category and isn't income.
- **Transfer**: money moving between your own accounts. It's never income or spending.
