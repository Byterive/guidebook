# PROJECT_STATUS

## Modules
| Module | Purpose | Status | Tests |
|---|---|---|---|
| order-reader | reads the orders file | PASSED | 12 tests |
| late-report | lists jobs past their due date | DOUBTFUL | 3 of 9 cases |
| csv-export | writes the late list to csv | UNTESTED | none |
| sms-notice | texts the customer | FAILED | 0 of 4 pass |
| due-date-rules | how due dates are worked out | UNKNOWN | not looked at |
| averyveryveryverylongmodulenamewithoutanyspacesthatwouldnotfitonaphonescreenatall | stress test for narrow screens | PASSED | 1 test |

## Risks
- The orders file has no backup.
- Customer phone numbers are stored in plain text.
