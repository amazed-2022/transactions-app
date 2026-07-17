#=================================================
# IMPORT
#=================================================
from models import Bank, CSVFormat, Category, Partner


#=================================================
# KNOWN BANK CSV FORMATS
#=================================================
KNOWN_BANK_FORMATS: list[CSVFormat] = [
    CSVFormat(
        bank=Bank.EXAMPLE,
        date_col="DATE COLUMN NAME",
        type_col="TYPE COLUMN NAME",
        partner_col="PARTNER COLUMN NAME",
        amount_col="AMOUNT COLUMN NAME",
        currency_col="CURRENCY COLUMN NAME",
        message_col="MESSAGE COLUMN NAME",
    ),
]

#=================================================
# PARTNER TO CATEGORY MAPPINGS
#=================================================
PARTNER_RULES: dict[Partner, Category] = {
    # Add exact partner-to-category mappings here

    # Grocery stores
    Partner.ALDI: Category.GROCERIES,
    Partner.LIDL: Category.GROCERIES,
    Partner.SPAR: Category.GROCERIES,

    # Drug stores
    Partner.MULLER_GROUP: Category.DRUG_STORE,
    Partner.DM_GROUP: Category.DRUG_STORE,

    # Household stores
    Partner.OBI_GROUP: Category.HOUSEHOLD,
    Partner.IKEA: Category.HOUSEHOLD,
    Partner.PRAKTIKER: Category.HOUSEHOLD,

    # etc.
    Partner.DECATHLON: Category.CLOTHES,
    Partner.OMV: Category.FUEL,
    Partner.TELEKOM: Category.UTILITIES,
}

PARTNER_ALIASES: dict[str, Partner] = {

    # Add partner name variants and aliases here.
    # These are used to normalize different raw transaction names
    # into a single Partner enum value

    "MÜLLER": Partner.MULLER_GROUP,
    "Mueller": Partner.MULLER_GROUP,
    "MULLER": Partner.MULLER_GROUP,
    "DM 144": Partner.DM_GROUP,
    "DM 205": Partner.DM_GROUP,
}

#=================================================
# HIGH-PRIORITY MESSAGE KEYWORD RULES
#=================================================
HIGH_PRIO_MESSAGE_RULES: dict[str, Category] = {
    # Add high-priority message keyword rules here

    # Example:
    "Salary": Category.SALARY,
}

#=================================================
# GENERAL KEYWORD TO CATEGORY MAPPINGS
#=================================================
LOW_PRIO_PARTNER_RULES: dict[str, Category] = {
    # Add general keyword-to-category mappings here

    # Examples:
    "Loan": Category.LOAN_REPAY,
    "ExampleShop": Category.GROCERIES,
}

# Optional user-specific overrides
try:
    import config_local

    KNOWN_BANK_FORMATS.extend(
        getattr(config_local, "KNOWN_BANK_FORMATS_LOCAL", [])
    )
    PARTNER_RULES.update(
        getattr(config_local, "PARTNER_RULES_LOCAL", {})
    )
    PARTNER_ALIASES.update(
        getattr(config_local, "PARTNER_ALIASES_LOCAL", {})
    )
    HIGH_PRIO_MESSAGE_RULES.update(
        getattr(config_local, "HIGH_PRIO_MESSAGE_RULES_LOCAL", {})
    )
    LOW_PRIO_PARTNER_RULES.update(
        getattr(config_local, "LOW_PRIO_PARTNER_RULES_LOCAL", {})
    )
except ImportError as e:
    print(e)