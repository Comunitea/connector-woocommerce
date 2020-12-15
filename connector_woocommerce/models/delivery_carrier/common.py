# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models, fields
from odoo.addons.component.core import Component


class WoocommerceDeliveryCarrier(models.Model):
    _name = "woo.delivery.carrier"
    _inherit = "woo.binding"
    _inherits = {"delivery.carrier": "odoo_id"}
    _description = "Woocommerce Carrier"

    odoo_id = fields.Many2one(
        comodel_name="delivery.carrier",
        string="Delivery carrier",
        required=True,
        ondelete="cascade",
        oldname="openerp_id",
    )


class CarrierAdapter(Component):

    _name = "woocommerce.delivery.carrier.adapter"
    _inherit = "woocommerce.adapter"
    _apply_on = "woo.delivery.carrier"

    _woo_model = "shipping_methods"

    def search(self, filters=None, from_date=None, to_date=None):
        """ Search records according to some criteria and return a
        list of ids

        :rtype: list
        """
        if filters is None:
            filters = {}
        objects = self._get(self._woo_model, filters)
        return [x["id"] for x in objects]
