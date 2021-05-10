# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "WooCommerce Connector",
    "version": "11.0.1.0.0",
    "category": "Connector",
    "author": "Tech Receptives,FactorLibre,Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "website": "http://www.openerp.com",
    "depends": ["connector", "sale_stock", "connector_ecommerce", "product_multi_category"],
    "installable": True,
    "auto_install": False,
    "data": [
        "security/ir.model.access.csv",
        "views/backend_view.xml",
        "views/account_payment_mode.xml",
        "views/sale.xml",
        "views/stock_location.xml",
        "views/product.xml",
        "views/res_partner.xml",
        "data/ir_cron.xml",
        "data/exception_rule.xml",
    ],
    "external_dependencies": {"python": ["woocommerce"]},
    "application": True,
    "sequence": 3,
}
