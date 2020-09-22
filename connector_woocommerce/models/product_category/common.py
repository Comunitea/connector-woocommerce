# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from odoo import models, fields
from odoo.addons.component.core import Component

_logger = logging.getLogger(__name__)


class WooProductCategory(models.Model):
    _name = "woo.product.category"
    _inherit = "woo.binding"
    _inherits = {"product.category": "odoo_id"}
    _description = "woo product category"

    _rec_name = "name"

    odoo_id = fields.Many2one(
        comodel_name="product.category",
        string="category",
        required=True,
        ondelete="cascade",
    )
    backend_id = fields.Many2one(
        comodel_name="wc.backend", string="Woo Backend", store=True, readonly=False
    )

    slug = fields.Char("Slug Name")
    woo_parent_id = fields.Many2one(
        comodel_name="woo.product.category",
        string="Woo Parent Category",
        ondelete="cascade",
    )
    description = fields.Char("Description")
    count = fields.Integer("count")


class CategoryAdapter(Component):
    _name = "woocommerce.product.category.adapter"
    _inherit = "woocommerce.adapter"
    _apply_on = "woo.product.category"

    _woo_model = "products/categories"
