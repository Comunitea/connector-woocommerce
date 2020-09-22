# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging

from contextlib import contextmanager
from odoo.addons.connector.models import checkpoint
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ...components.backend_adapter import WooLocation, WooAPI

_logger = logging.getLogger(__name__)

try:
    from woocommerce import API
except ImportError:
    _logger.debug("Cannot import 'woocommerce'")

IMPORT_DELTA_BUFFER = 30  # seconds


class WooBackend(models.Model):
    _name = "wc.backend"
    _inherit = "connector.backend"
    _description = "WooCommerce Backend Configuration"

    @api.model
    def select_versions(self):
        """ Available versions in the backend.

        Can be inherited to add custom versions.  Using this method
        to add a version from an ``_inherit`` does not constrain
        to redefine the ``version`` field in the ``_inherit`` model.
        """
        return [("v2", "V2")]

    name = fields.Char("Name", required=True)
    location = fields.Char("Url", required=True)
    consumer_key = fields.Char("Consumer key")
    consumer_secret = fields.Char("Consumer Secret")
    version = fields.Selection(selection="select_versions", required=True)
    verify_ssl = fields.Boolean("Verify SSL")
    warehouse_id = fields.Many2one(
        comodel_name="stock.warehouse",
        string="Warehouse",
        required=True,
        help="Warehouse used to compute the " "stock quantities.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        related="warehouse_id.company_id",
        string="Company",
        readonly=True,
    )
    default_lang_id = fields.Many2one(
        comodel_name="res.lang",
        string="Default Language",
        help="If a default language is selected, the records "
        "will be imported in the translation of this language.\n"
        "Note that a similar configuration exists "
        "for each storeview.",
    )
    import_product_categories_since = fields.Datetime()
    import_products_since = fields.Datetime()
    import_customers_since = fields.Datetime()
    import_customers_since = fields.Datetime()
    import_orders_since = fields.Datetime()
    importable_order_state_ids = fields.Many2many(
        comodel_name="woo.sale.order.status",
        string="Importable sale order states",
        help="If valued only orders matching these states will be imported.",
    )
    shipping_product_id = fields.Many2one(
        "product.template", required=True, string="Shipping Product"
    )
    fee_product_id = fields.Many2one(
        "product.template", required=True, string="Fees Product"
    )
    matching_product = fields.Boolean(string="Match product")
    product_qty_field = fields.Selection(
        selection=[
            ("qty_available_not_res", "Immediately usable qty"),
            ("qty_available", "Qty available"),
        ],
        string="Product qty",
        help="Select how you want to calculate the qty to push to Woocommerce. ",
        default="qty_available",
        required=True,
    )
    stock_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Stock Location",
        help="Location used to import stock quantities.",
    )
    sale_team_id = fields.Many2one('crm.team', 'Sales Team',
        help="Sales Team assigned to the imported sales orders.",
    )
    partner_vat_field = fields.Char("Metadata field for vat number")

    @api.multi
    def add_checkpoint(self, record, message=""):
        """
        @param message: used with this
        https://github.com/OCA/connector/issues/37
        """
        self.ensure_one()
        record.ensure_one()
        chk_point = checkpoint.add_checkpoint(
            self.env, record._name, record.id, self._name, self.id
        )
        if message:
            chk_point.message_post(body=message)
        return chk_point

    @api.constrains("product_qty_field")
    def check_product_qty_field_dependencies_installed(self):
        for backend in self:
            # we only support stock_available_unreserved module for now.
            # In order to support stock_available_immediately or
            # virtual_available for example, we would need to recompute
            # the woocommerce qty at stock move level, it can't work to
            # recompute it only at quant level, like it is done today
            if backend.product_qty_field == "qty_available_not_res":
                module = (
                    self.env["ir.module.module"]
                    .sudo()
                    .search([("name", "=", "stock_available_unreserved")], limit=1)
                )
                if not module or module.state != "installed":
                    raise UserError(
                        _(
                            "In order to choose this option, you have to "
                            "install the module stock_available_unreserved."
                        )
                    )

    @api.multi
    def _get_locations_for_stock_quantities(self):
        root_location = self.stock_location_id or self.warehouse_id.lot_stock_id
        locations = self.env["stock.location"].search(
            [
                ("id", "child_of", root_location.id),
                ("woo_synchronized", "=", True),
                ("usage", "=", "internal"),
            ]
        )
        # if we choosed a location but none where flagged
        # 'woo_synchronized', consider we want all of them in the tree
        if not locations:
            locations = self.env["stock.location"].search(
                [("id", "child_of", root_location.id), ("usage", "=", "internal")]
            )
        if not locations:
            # we must not pass an empty location or we would have the
            # stock for every warehouse, which is the last thing we
            # expect
            raise UserError(
                _("No internal location found to compute the product " "quantity.")
            )
        return locations

    @contextmanager
    @api.multi
    def work_on(self, model_name, **kwargs):
        self.ensure_one()
        # lang = self.default_lang_id
        # if lang.code != self.env.context.get('lang'):
        #     self = self.with_context(lang=lang.code)
        woocommerce_location = WooLocation(
            self.location, self.consumer_key, self.consumer_secret
        )
        # TODO: Check Auth Basic
        # if self.use_auth_basic:
        #     magento_location.use_auth_basic = True
        #     magento_location.auth_basic_username = self.auth_basic_username
        #     magento_location.auth_basic_password = self.auth_basic_password
        wc_api = WooAPI(woocommerce_location)
        _super = super(WooBackend, self)
        with _super.work_on(model_name, wc_api=wc_api, **kwargs) as work:
            yield work

    @api.multi
    def get_product_ids(self, data):
        product_ids = [x["id"] for x in data["products"]]
        product_ids = sorted(product_ids)
        return product_ids

    @api.multi
    def get_product_category_ids(self, data):
        product_category_ids = [x["id"] for x in data["product_categories"]]
        product_category_ids = sorted(product_category_ids)
        return product_category_ids

    @api.multi
    def get_customer_ids(self, data):
        customer_ids = [x["id"] for x in data["customers"]]
        customer_ids = sorted(customer_ids)
        return customer_ids

    @api.multi
    def get_order_ids(self, data):
        order_ids = self.check_existing_order(data)
        return order_ids

    @api.multi
    def update_existing_order(self, woo_sale_order, data):
        """ Enter Your logic for Existing Sale Order """
        return True

    @api.multi
    def check_existing_order(self, data):
        order_ids = []
        for val in data["orders"]:
            woo_sale_order = self.env["woo.sale.order"].search(
                [("external_id", "=", val["id"])]
            )
            if woo_sale_order:
                self.update_existing_order(woo_sale_order[0], val)
                continue
            order_ids.append(val["id"])
        return order_ids

    @api.multi
    def test_connection(self):
        location = self.location
        cons_key = self.consumer_key
        sec_key = self.consumer_secret

        wcapi = API(
            url=location,
            consumer_key=cons_key,
            consumer_secret=sec_key,
            wp_api=True,
            version="wc/v2",
        )
        r = wcapi.get("products")
        if r.status_code == 404:
            raise UserError(_("Enter Valid url"))
        val = r.json()
        msg = ""
        if "errors" in r.json():
            msg = val["errors"][0]["message"] + "\n" + val["errors"][0]["code"]
            raise UserError(_(msg))
        else:
            raise UserError(_("Test Success"))
        return True

    @api.multi
    def import_categories(self):
        for backend in self:
            since_date = backend.import_product_categories_since
            self.env["woo.product.category"].with_delay().import_batch(
                backend, filters={"from_date": since_date}
            )
            backend.import_product_categories_since = fields.Datetime.now()
        return True

    @api.multi
    def import_products(self):
        for backend in self:
            since_date = backend.import_products_since
            self.env["woo.product.template"].with_delay().import_batch(
                backend, filters={"from_date": since_date}
            )
            backend.import_products_since = fields.Datetime.now()
        return True

    @api.multi
    def import_customers(self):
        for backend in self:
            since_date = backend.import_customers_since
            self.env["woo.res.partner"].with_delay().import_batch(
                backend, filters={"from_date": since_date}
            )
            backend.import_customers_since = fields.Datetime.now()
        return True

    @api.multi
    def import_orders(self):
        for backend in self:
            since_date = backend.import_orders_since
            self.env["woo.sale.order"].with_delay().import_batch(
                backend, filters={"from_date": since_date}
            )
            backend.import_orders_since = fields.Datetime.now()
        return True

    @api.multi
    def import_carriers(self):
        for backend in self:
            self.env["woo.delivery.carrier"].with_delay().import_batch(backend)
        return True

    @api.model
    def _scheduler_import_customers(self, domain=None):
        self.search(domain or []).import_customers()

    @api.model
    def _scheduler_import_sale_orders(self, domain=None):
        self.search(domain or []).import_orders()

    @api.model
    def _scheduler_import_products(self, domain=None):
        self.search(domain or []).import_products()
