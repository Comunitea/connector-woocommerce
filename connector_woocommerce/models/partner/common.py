# © 2009 Tech-Receptives Solutions Pvt. Ltd.
# © 2018 FactorLibre
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from odoo import models, fields
from odoo.addons.component.core import Component

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    woo_bind_ids = fields.One2many("woo.res.partner", "odoo_id", "Woocommerce binds")


class WooResPartner(models.Model):
    _name = "woo.res.partner"
    _inherit = "woo.binding"
    _inherits = {"res.partner": "odoo_id"}
    _description = "woo res partner"

    _rec_name = "name"

    odoo_id = fields.Many2one(
        comodel_name="res.partner", string="Partner", required=True, ondelete="cascade"
    )
    backend_id = fields.Many2one(
        comodel_name="wc.backend", string="Woo Backend", store=True, readonly=False
    )
    woo_vatnumber = fields.Char()


class CustomerAdapter(Component):

    _name = "woocommerce.partner.adapter"
    _inherit = "woocommerce.adapter"
    _apply_on = "woo.res.partner"

    _woo_model = "customers"
