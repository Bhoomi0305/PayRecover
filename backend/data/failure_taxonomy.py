FAILURE_TAXONOMY = {
    "INSUFFICIENT_FUNDS": {
        "description": "Customer's account/card had insufficient balance",
        "recoverable": True,
        "default_strategy": "DELAYED_RETRY",
    },
    "GATEWAY_TIMEOUT": {
        "description": "Bank or gateway server did not respond in time",
        "recoverable": True,
        "default_strategy": "IMMEDIATE_RETRY",
    },
    "OTP_FAILED": {
        "description": "Wrong OTP entered or OTP expired",
        "recoverable": True,
        "default_strategy": "NOTIFY_AND_RETRY",
    },
    "CARD_DECLINED_BY_ISSUER": {
        "description": "Issuing bank declined this specific transaction",
        "recoverable": True,
        "default_strategy": "SUGGEST_ALT_METHOD",
    },
    "RISK_BLOCKED": {
        "description": "Gateway risk engine flagged transaction as suspicious",
        "recoverable": False,
        "default_strategy": "ESCALATE_HUMAN",
    },
    "INVALID_CARD_DETAILS": {
        "description": "Expired card, wrong CVV, or invalid card number",
        "recoverable": False,
        "default_strategy": "NOTIFY_CUSTOMER_ONLY",
    },
    "DAILY_LIMIT_EXCEEDED": {
        "description": "Customer exceeded their bank's daily transaction limit",
        "recoverable": True,
        "default_strategy": "DELAYED_RETRY",
    },
    "NETWORK_ERROR": {
        "description": "Connection dropped during payment",
        "recoverable": True,
        "default_strategy": "IMMEDIATE_RETRY",
    },
    "AMBIGUOUS": {
        "description": "Raw failure message doesn't map to a known code",
        "recoverable": None,  # unknown until classified
        "default_strategy": None,
    },
}

METHOD_COMPATIBLE_CODES = {
    "card": [
        "INSUFFICIENT_FUNDS",
        "CARD_DECLINED_BY_ISSUER",
        "INVALID_CARD_DETAILS",
        "RISK_BLOCKED",
        "GATEWAY_TIMEOUT",
        "DAILY_LIMIT_EXCEEDED",
    ],
    "upi": [
        "INSUFFICIENT_FUNDS",
        "OTP_FAILED",
        "DAILY_LIMIT_EXCEEDED",
        "NETWORK_ERROR",
        "RISK_BLOCKED",
        "GATEWAY_TIMEOUT",
    ],
    "netbanking": [
        "INSUFFICIENT_FUNDS",
        "GATEWAY_TIMEOUT",
        "NETWORK_ERROR",
        "DAILY_LIMIT_EXCEEDED",
        "RISK_BLOCKED",
    ],
    "wallet": [
        "INSUFFICIENT_FUNDS",
        "DAILY_LIMIT_EXCEEDED",
        "NETWORK_ERROR",
        "RISK_BLOCKED",
    ],
}

# Sample of realistic messy raw bank/gateway messages for cases we want
# the LLM to classify instead of a clean code lookup
AMBIGUOUS_RAW_MESSAGES = [
    "Txn declined by issuing bank. Contact your bank for details.",
    "Payment could not be completed due to a temporary issue. Please try again.",
    "Your bank has declined this transaction. RC: 51",
    "Authentication failed at bank end.",
    "Transaction timed out while waiting for bank response.",
    "Card issuer declined - do not honour.",
    "Payment failed - risk check unsuccessful.",
    "Unable to process - account restrictions apply.",
]
