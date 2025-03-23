import bpy
from bpy.types import Operator

from . utils.select_utils import *

class JB_Bake_Op(Operator):
    bl_idname = "object.bake_op"
    bl_label = "Bake maps"
    bl_description = "Bake image maps for low and high poly objects"
    bl_options = {'REGISTER'}

    def execute(self, context):
        self.__baking = True

        low_poly = context.scene.low_poly
        high_poly = context.scene.high_poly

        if not low_poly or not high_poly:
            self.report({'ERROR'}, "Low or High Poly object not set.")
            return {'CANCELLED'}

        if len(low_poly.data.materials) == 0:
            self.report({'ERROR'}, f"Assign a material to {low_poly.name} before baking.")
            return {'CANCELLED'}    

        node_tree = low_poly.data.materials[0].node_tree

        # Check for principled shader
        pri_shader_node = self.get_node("BSDF_PRINCIPLED", node_tree)
        if pri_shader_node is None:
            self.report({'ERROR'}, "Principled BSDF not found in material.")
            return {'CANCELLED'}

        # Set render engine to Cycles
        render_engine_old = context.scene.render.engine
        context.scene.render.engine = 'CYCLES'

        low_poly.hide_set(False)
        low_poly.select_set(True)
        bpy.context.view_layer.objects.active = low_poly
        bpy.ops.object.mode_set(mode='OBJECT')

        self.create_normal_map(node_tree, pri_shader_node, context)

        hp_hide = high_poly.hide_get()
        high_poly.hide_set(False)
        high_poly.select_set(True)
        low_poly.select_set(True)
        bpy.context.view_layer.objects.active = low_poly

        self.bake_normal_map()

        high_poly.hide_set(hp_hide)
        bpy.context.view_layer.objects.active = None

        # Reset render engine
        context.scene.render.engine = render_engine_old
        self.__baking = False

        return {'FINISHED'}

    def create_normal_map(self, node_tree, pri_shader_node, context):
        # Check if there is a normal map attached already.
        # If not, create a normal map and attach it
        normal_map_node = None
        if not pri_shader_node.inputs["Normal"].is_linked:
            normal_map_node = self.create_normal_map_node(node_tree)
            self.add_link(node_tree, normal_map_node, pri_shader_node, "Normal", "Normal")
        else:
            normal_map_node = pri_shader_node.inputs["Normal"].links[0].from_node

        # Check if the normal map has an image texture assigned
        # If not, create an image texture node and attach it
        normal_img_node = None
        if not normal_map_node.inputs["Color"].is_linked:
            normal_img_node = self.create_normal_img_node(node_tree, context)       
            self.add_link(node_tree, normal_img_node, normal_map_node, "Color", "Color", True)
        else:
            normal_img_node = normal_map_node.inputs["Color"].links[0].from_node

    def create_normal_img_node(self, node_tree, context):
        img_node = node_tree.nodes.new('ShaderNodeTexImage')
        img_name = context.scene.low_poly.name + "_normal"
        img_width = context.scene.img_bake_width
        img_height = context.scene.img_bake_height

        # Ensure width and height are set correctly
        if img_width <= 0 or img_height <= 0:
            img_width, img_height = 2048, 2048  # Fallback to default values

        image = bpy.data.images.new(img_name, width=img_width, height=img_height)
        image.colorspace_settings.name = "Non-Color"

        img_node.image = image
        return img_node

    def create_normal_map_node(self, node_tree):
        return node_tree.nodes.new('ShaderNodeNormalMap')

    def get_node(self, node_type, node_tree):
        for node in node_tree.nodes:
            if node.type == node_type:
                return node
        return None

    def bake_normal_map(self):
        bpy.ops.object.bake(type="NORMAL", use_selected_to_active=True)

    def add_link(self, node_tree, node, node2, output_name, input_name, non_color_data=False):
        """Create a link between nodes and set color space if applicable"""
        node_tree.links.new(node.outputs[output_name], node2.inputs[input_name])
        
        if hasattr(node, "image") and non_color_data:
            node.image.colorspace_settings.name = "Non-Color"
