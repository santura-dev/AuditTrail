from prometheus_client import Counter

# Count how many logs have been created
log_created_counter = Counter(
    'audittrail_logs_created_total',
    'Total number of logs created'
)

# Count how many times logs have been listed
log_listed_counter = Counter(
    'audittrail_logs_listed_total',
    'Total number of times logs have been listed'
)