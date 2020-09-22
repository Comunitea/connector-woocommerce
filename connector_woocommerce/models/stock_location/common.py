# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class StockLocation(models.Model):
    _inherit = "stock.location"

    woo_synchronized = fields.Boolean(
        string="Sync with Woocommerce",
        help="Check this option to synchronize this location with Woocommerce",
    )

    @api.model
    def get_woocommerce_stock_locations(self):
        woocommerce_locations = self.search(
            [("woo_synchronized", "=", True), ("usage", "=", "internal")]
        )
        return woocommerce_locations
