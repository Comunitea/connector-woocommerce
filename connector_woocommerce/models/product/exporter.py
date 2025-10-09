# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.addons.component.core import Component


class ProductInventoryExporter(Component):
    _name = "woo.product.template.inventory.exporter"
    _inherit = "woocommerce.exporter"
    _apply_on = "woo.product.template"
    _usage = "inventory.exporter"
    _woo_model = "products"

    def get_quantity_vals(self, product):
        if not product.manage_stock:
            return {"in_stock": int(product.quantity) > 0}
        else:
            return {"stock_quantity": int(product.quantity)}

    def run(self, product, fields):
        self.backend_adapter.write(product.external_id, self.get_quantity_vals(product))
