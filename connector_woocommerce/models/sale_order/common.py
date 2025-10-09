# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


WOO_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"
import logging
import odoo.addons.decimal_precision as dp
from odoo import models, fields, api
from odoo.addons.component.core import Component

_logger = logging.getLogger(__name__)


class WooSaleOrderStatus(models.Model):
    _name = "woo.sale.order.status"
    _description = "WooCommerce Sale Order Status"

    name = fields.Char("Name")
    desc = fields.Text("Description")


class SaleOrder(models.Model):
    _inherit = "sale.order"

    woo_bind_ids = fields.One2many("woo.sale.order", "odoo_id", "Woocommerce Bindings")


class WooSaleOrder(models.Model):
    _name = "woo.sale.order"
    _inherit = "woo.binding"
    _inherits = {"sale.order": "odoo_id"}
    _description = "Woo Sale Order"

    _rec_name = "name"

    status_id = fields.Many2one("woo.sale.order.status", "WooCommerce Order Status")

    odoo_id = fields.Many2one(
        comodel_name="sale.order",
        string="Sale Order",
        required=True,
        ondelete="cascade",
    )
    woo_order_line_ids = fields.One2many(
        comodel_name="woo.sale.order.line",
        inverse_name="woo_order_id",
        string="Woo Order Lines",
    )
    backend_id = fields.Many2one(
        comodel_name="wc.backend",
        string="Woo Backend",
        store=True,
        readonly=False,
        required=True,
    )
    total_amount = fields.Float(
        string="Total amount in Woocommerce",
        digits=dp.get_precision("Account"),
        readonly=True,
    )
    total_amount_tax = fields.Float(
        string="Total tax in Woocommerce",
        digits=dp.get_precision("Account"),
        readonly=True,
    )
    total_shipping_tax_excluded = fields.Float(
        string="Total shipping in Woocommerce",
        digits=dp.get_precision("Account"),
        readonly=True,
    )


class WooSaleOrderLine(models.Model):
    _name = "woo.sale.order.line"
    _inherits = {"sale.order.line": "odoo_id"}

    woo_order_id = fields.Many2one(
        comodel_name="woo.sale.order",
        string="Woo Sale Order",
        required=True,
        ondelete="cascade",
        index=True,
    )

    odoo_id = fields.Many2one(
        comodel_name="sale.order.line",
        string="Sale Order Line",
        required=True,
        ondelete="cascade",
    )

    backend_id = fields.Many2one(
        related="woo_order_id.backend_id",
        string="Woo Backend",
        readonly=True,
        store=True,
        required=False,
    )

    @api.model
    def create(self, vals):
        woo_order_id = vals["woo_order_id"]
        binding = self.env["woo.sale.order"].browse(woo_order_id)
        vals["order_id"] = binding.odoo_id.id
        binding = super(WooSaleOrderLine, self).create(vals)
        return binding


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    woo_bind_ids = fields.One2many(
        comodel_name="woo.sale.order.line",
        inverse_name="odoo_id",
        string="WooCommerce Bindings",
    )


class SaleOrderAdapter(Component):
    _name = "woocommerce.sale.order.adapater"
    _inherit = "woocommerce.adapter"
    _apply_on = "woo.sale.order"

    _woo_model = "orders"

    def search(self, filters=None, from_date=None, to_date=None):
        """ Search records according to some criteria and return a
        list of ids

        :rtype: list
        """
        if filters is None:
            filters = {}
        dt_fmt = WOO_DATETIME_FORMAT
        filters["per_page"] = 25
        if from_date:
            # updated_at include the created records
            filters["after"] = from_date.strftime(dt_fmt)
        if to_date:
            filters["before"] = to_date.strftime(dt_fmt)
        objects_data = self._get(self._woo_model, filters)
        objects = objects_data
        readed = len(objects)
        while objects_data:
            filters["offset"] = readed
            objects_data = self._get(self._woo_model, filters)
            readed += len(objects_data)
            objects = objects + objects_data
        return [x["id"] for x in objects]
