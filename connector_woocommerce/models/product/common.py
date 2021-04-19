# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from collections import defaultdict
from odoo import api, models, fields
from odoo.addons.queue_job.job import job
from odoo.addons.component.core import Component
from odoo.addons.component_event import skip_if

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    woo_bind_ids = fields.One2many(
        "woo.product.template", "odoo_id", "Woocommerce Bindings"
    )

    def write(self, vals):
        if vals.get("image"):
            vals["image_main"] = vals["image"]
        return super().write(vals)

    @api.multi
    def update_woo_qty(self):
        for product in self:
            for woo_product in product.woo_bind_ids:
                woo_product.recompute_woo_qty()


class WooProductTemplate(models.Model):
    _name = "woo.product.template"
    _inherit = "woo.binding"
    _inherits = {"product.template": "odoo_id"}
    _description = "woo product product"

    _rec_name = "name"
    odoo_id = fields.Many2one(
        comodel_name="product.template",
        string="product",
        required=True,
        ondelete="cascade",
    )
    backend_id = fields.Many2one(
        comodel_name="wc.backend",
        string="Woo Backend",
        store=True,
        readonly=False,
        required=True,
    )
    manage_stock = fields.Boolean()
    slug = fields.Char("Slug Name")
    credated_at = fields.Date("created_at")
    weight = fields.Float("weight")
    quantity = fields.Float(
        string="Computed Quantity",
        help="Last computed quantity to send to Woocommerce.",
    )

    @job(default_channel="root.woocommerce")
    def export_inventory(self, fields=None):
        """ Export the inventory configuration and quantity of a product. """
        backend = self.backend_id
        with backend.work_on("woo.product.template") as work:
            exporter = work.component(usage="inventory.exporter")
            return exporter.run(self, fields)

    @job(default_channel="root.woocommerce")
    def export_product_quantities(self, backend=None):
        self.search([("backend_id", "=", backend.id)]).recompute_woo_qty()

    @api.multi
    def recompute_woo_qty(self):
        # group products by backend
        backends = defaultdict(set)
        for product in self:
            backends[product.backend_id].add(product.id)

        for backend, product_ids in backends.items():
            products = self.browse(product_ids)
            products._recompute_woo_qty_backend(backend)
        return True

    @api.multi
    def _recompute_woo_qty_backend(self, backend):
        locations = backend._get_locations_for_stock_quantities()
        self_loc = self.with_context(location=locations.ids, compute_child=False)
        for product_binding in self_loc:
            new_qty = product_binding._woo_qty(backend)
            if product_binding.quantity != new_qty:
                product_binding.quantity = new_qty
        return True

    def _woo_qty(self, backend):
        qty = self[backend.product_qty_field]
        if qty < 0:
            # make sure we never send negative qty to PS
            # because the overall qty computed at template level
            # is going to be wrong.
            qty = 0.0
        return qty


class ProductTemplateAdapter(Component):
    _name = "woocommerce.product.template.adapter"
    _inherit = "woocommerce.adapter"
    _apply_on = "woo.product.template"

    _woo_model = "products"


class WoocommerceProductQuantityListener(Component):
    _name = "woocommerce.product.quantity.listener"
    _inherit = "base.connector.listener"
    _apply_on = ["woo.product.template"]

    def _get_inventory_fields(self):
        # fields which should not trigger an export of the products
        # but an export of their inventory
        return ("quantity", "manage_stock")

    @skip_if(lambda self, record, **kwargs: self.no_connector_export(record))
    def on_record_write(self, record, fields=None):
        inventory_fields = list(set(fields).intersection(self._get_inventory_fields()))
        if inventory_fields:
            record.with_delay(priority=20).export_inventory(fields=inventory_fields)
