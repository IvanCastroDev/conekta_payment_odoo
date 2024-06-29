{
    # App information
    "name": "Conekta/OXXO/SPEI Payment Acquirer",
    "version": "16.0.1.1.4",
    "category": "Accounting",
    "summary": """Payment Acquirer: Conekta / OXOO Cash Payment / SPEI Cash Payment.Do payment same way like standard Payment method availables like Paypal,Square,Amazon,Openpay,authorize,stripe,iPay""",
    "license": "OPL-1",
    "depends": ["payment", "website_sale"],
    # Views
    "data": [
        "views/payment_views.xml",
        "report/transaction_report.xml",
        "report/transaction_report_template_oxxo.xml",
        "report/transaction_report_template_spei.xml",
        "views/payment_conekta_templates.xml",
        "data/payment_provider_data.xml",
        "views/payment_portal_templates.xml",
    ],
    "images": ["static/description/conekta_banner.png"],
    # Assets
    "assets": {
        "web.report_assets_common": [
            ("include", "web._assets_helpers"),
            "payment_conekta_oxoo/static/src/scss/style.scss",
        ],
        "web.assets_frontend": [
            "https://conektaapi.s3.amazonaws.com/v0.3.2/js/conekta.js",
            "https://pay.conekta.com/v1.0/js/conekta-checkout.min.js",
            "payment_conekta_oxoo/static/src/scss/style.scss",
            "payment_conekta_oxoo/static/src/js/payment_form.js",
            "payment_conekta_oxoo/static/src/js/post_processing.js",
            "payment_conekta_oxoo/static/src/js/browse_error.js",
        ],
    },
    # only loaded in demonstration mode
    "demo": [],
    # Author
    "author": "Synodica Solutions Pvt. Ltd.",
    "website": "https://synodica.com",
    "maintainer": "Synodica Solutions Pvt. Ltd.",
    # Technical
    "installable": True,
    "auto_install": False,
    "application": True,
    "price": "449",
    "currency": "USD",
    "uninstall_hook": "uninstall_hook",
}
