import json

from django.contrib.auth.models import User
from django.db.models import Prefetch
from django.template.loader import render_to_string
from rest_framework import serializers
from rest_framework.reverse import reverse

from mothra.settings import STATIC_URL, MEDIA_URL
from workflows.models import *


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ('username',)


class AbstractOptionSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = AbstractOption
        fields = ('name', 'value')
        read_only_fields = ('name', 'value')


class AbstractInputSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField()
    options = AbstractOptionSerializer(many=True, read_only=True)

    class Meta:
        model = AbstractInput
        fields = (
            'id', 'name', 'short_name', 'description', 'variable', 'required', 'parameter', 'multi', 'default',
            'parameter_type',
            'order', 'options')
        read_only_fields = (
            'id', 'name', 'short_name', 'description', 'variable', 'required', 'parameter', 'multi', 'default',
            'parameter_type',
            'order', 'options')


class AbstractOutputSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField()

    class Meta:
        model = AbstractOutput
        fields = ('id', 'name', 'short_name', 'description', 'variable', 'order')
        read_only_fields = ('id', 'name', 'short_name', 'description', 'variable', 'order')


class AbstractWidgetSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField()
    inputs = AbstractInputSerializer(many=True, read_only=True)
    outputs = AbstractOutputSerializer(many=True, read_only=True)
    cfpackage = serializers.SerializerMethodField()

    def get_cfpackage(self, obj):
        return obj.package

    class Meta:
        model = AbstractWidget
        fields = ('id', 'name', 'interactive', 'static_image', 'order', 'outputs', 'inputs', 'cfpackage')
        read_only_fields = ('id', 'name', 'interactive', 'static_image', 'order', 'outputs', 'inputs', 'cfpackage')


class CategorySerializer(serializers.HyperlinkedModelSerializer):
    widgets = AbstractWidgetSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ('name', 'user', 'order', 'children', 'widgets')
        read_only_fields = ('name', 'user', 'order', 'children', 'widgets')


CategorySerializer._declared_fields['children'] = CategorySerializer(many=True, read_only=True)


class ConnectionSerializer(serializers.HyperlinkedModelSerializer):
    output_widget = serializers.SerializerMethodField()
    input_widget = serializers.SerializerMethodField()

    def get_output_widget(self, obj):
        request = self.context['request']
        return request.build_absolute_uri(reverse('widget-detail', kwargs={'pk': obj.output.widget_id}))
        # return WidgetListSerializer(obj.output.widget, context=self.context).data["url"]

    def get_input_widget(self, obj):
        request = self.context['request']
        return request.build_absolute_uri(reverse('widget-detail', kwargs={'pk': obj.input.widget_id}))
        # return WidgetListSerializer(obj.input.widget, context=self.context).data["url"]

    class Meta:
        model = Connection


class OptionSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Option
        fields = ('name', 'value')


class InputSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField(read_only=True)
    deserialized_value = serializers.SerializerMethodField()
    options = OptionSerializer(many=True, read_only=True)
    abstract_input_id = serializers.SerializerMethodField()

    def get_deserialized_value(self, obj):
        if obj.parameter:
            try:
                json.dumps(obj.value)
            except:
                return repr(obj.value)
            else:
                return obj.value
        else:
            return ''

    def get_abstract_input_id(self, obj):
        return obj.abstract_input_id

    class Meta:
        model = Input
        exclude = ('value', 'abstract_input')
        read_only_fields = ('id', 'url', 'widget')


class OutputSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField(read_only=True)
    abstract_output_id = serializers.SerializerMethodField()

    def get_abstract_output_id(self, obj):
        return obj.abstract_output_id

    class Meta:
        model = Output
        exclude = ('value', 'abstract_output')
        read_only_fields = ('id', 'url', 'widget')


def get_workflow_preview(request, obj):
    min_x = 10000
    min_y = 10000
    max_x = 0
    max_y = 0
    max_width = 300
    max_height = 200
    normalized_values = {}
    obj.normalized_widgets = obj.widgets.all()
    obj.unique_connections = []
    obj.pairs = []
    for widget in obj.normalized_widgets:
        if widget.x > max_x:
            max_x = widget.x
        if widget.x < min_x:
            min_x = widget.x
        if widget.y > max_y:
            max_y = widget.y
        if widget.y < min_y:
            min_y = widget.y
    for widget in obj.normalized_widgets:
        x = (widget.x - min_x) * 1.0
        y = (widget.y - min_y) * 1.0
        normalized_max_x = max_x - min_x
        if x == 0:
            x = 1
        if y == 0:
            y = 1
        if normalized_max_x == 0:
            normalized_max_x = x * 2
        normalized_max_y = max_y - min_y
        if normalized_max_y == 0:
            normalized_max_y = y * 2
        widget.norm_x = (x / normalized_max_x) * max_width
        widget.norm_y = (y / normalized_max_y) * max_height
        normalized_values[widget.id] = (widget.norm_x, widget.norm_y)
    for c in obj.connections.select_related("output", "input").defer("output__value", "input__value").all():
        if not (c.output.widget_id, c.input.widget_id) in obj.pairs:
            obj.pairs.append((c.output.widget_id, c.input.widget_id))
    for pair in obj.pairs:
        conn = {}
        conn['x1'] = normalized_values[pair[0]][0] + 40
        conn['y1'] = normalized_values[pair[0]][1] + 15
        conn['x2'] = normalized_values[pair[1]][0] - 10
        conn['y2'] = normalized_values[pair[1]][1] + 15
        obj.unique_connections.append(conn)
    base_url = request.build_absolute_uri('/')[:-1]
    images_url = '{}{}'.format(base_url, STATIC_URL)
    preview_html = render_to_string('preview.html', {'w': obj, 'images_url': images_url})
    return preview_html


class WorkflowListSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField(read_only=True)
    user = UserSerializer(read_only=True)
    is_subprocess = serializers.SerializerMethodField()
    is_public = serializers.BooleanField(source='public')

    def get_is_subprocess(self, obj):
        if obj.widget == None:
            return False
        else:
            return True

    class Meta:
        model = Workflow
        exclude = ('public',)


class WorkflowPreviewSerializer(WorkflowListSerializer):
    preview = serializers.SerializerMethodField()

    def get_preview(self, obj):
        return get_workflow_preview(self.context['request'], obj)


class WidgetSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField(read_only=True)
    inputs = InputSerializer(many=True, read_only=True)
    outputs = OutputSerializer(many=True, read_only=True)
    description = serializers.CharField(source='abstract_widget.description', read_only=True)
    icon = serializers.SerializerMethodField()
    must_save = serializers.SerializerMethodField()
    workflow_link = serializers.HyperlinkedRelatedField(
        read_only=True,
        view_name='workflow-detail'
    )
    abstract_widget = serializers.PrimaryKeyRelatedField(queryset=AbstractWidget.objects.all(), allow_null=True)

    def create(self, validated_data):
        '''
        Overrides the default create method to support nested creates
        '''
        w = Widget.objects.create(**validated_data)
        aw = w.abstract_widget
        input_order, param_order = 0, 0
        for i in aw.inputs.all():
            j = Input()
            j.name = i.name
            j.short_name = i.short_name
            j.description = i.description
            j.variable = i.variable
            j.widget = w
            j.required = i.required
            j.parameter = i.parameter
            j.value = None
            j.abstract_input = i
            if (i.parameter):
                param_order += 1
                j.order = param_order
            else:
                input_order += 1
                j.order = input_order
            if not i.multi:
                j.value = i.default
            j.parameter_type = i.parameter_type
            if i.multi:
                j.multi_id = i.id
            j.save()
            for k in i.options.all():
                o = Option()
                o.name = k.name
                o.value = k.value
                o.input = j
                o.save()
        outputOrder = 0
        for i in aw.outputs.all():
            j = Output()
            j.name = i.name
            j.short_name = i.short_name
            j.description = i.description
            j.variable = i.variable
            j.widget = w
            j.abstract_output = i
            outputOrder += 1
            j.order = outputOrder
            j.save()
        w.defered_outputs = w.outputs.defer("value").all()
        w.defered_inputs = w.inputs.defer("value").all()
        return w

    def update(self, widget, validated_data):
        '''
        Overrides the default update method to support nested creates
        '''
        # Ignore inputs and outputs on patch - we allow only nested creates
        if 'inputs' in validated_data:
            validated_data.pop('inputs')
        if 'outputs' in validated_data:
            validated_data.pop('outputs')
        widget, _ = Widget.objects.update_or_create(pk=widget.pk, defaults=validated_data)
        if widget.type == 'subprocess':
            widget.workflow_link.name = widget.name
            widget.workflow_link.save()
        return widget

    def get_must_save(self, widget):
        '''
        Some widget always require their inputs and outputs to be saved.
        '''
        must_save = False
        if widget.abstract_widget:
            must_save = widget.abstract_widget.interactive
        return must_save

    def get_icon(self, widget):
        full_path_tokens = self.context['request'].build_absolute_uri().split('/')
        protocol = full_path_tokens[0]
        base_url = full_path_tokens[2]
        icon_path = 'special_icons/question-mark.png'
        static_or_media = STATIC_URL
        if widget.abstract_widget:
            if widget.abstract_widget.static_image:
                icon_path = '{}/icons/widget/{}'.format(widget.abstract_widget.package,
                                                        widget.abstract_widget.static_image)
            elif widget.abstract_widget.image:
                static_or_media = MEDIA_URL
                icon_path = widget.abstract_widget.image
            elif widget.abstract_widget.wsdl:
                icon_path = 'special_icons/ws.png'
        elif hasattr(widget, 'workflow_link'):
            icon_path = 'special_icons/subprocess.png'
        elif widget.type == 'input':
            icon_path = 'special_icons/forward-arrow.png'
        elif widget.type == 'output':
            icon_path = 'special_icons/forward-arrow.png'
        elif widget.type == 'output':
            icon_path = 'special_icons/loop.png'
        icon_url = '{}//{}{}{}'.format(protocol, base_url, static_or_media, icon_path)
        return icon_url

    class Meta:
        model = Widget
        fields = (
            'id', 'url', 'workflow', 'x', 'y', 'name', 'save_results', 'must_save', 'abstract_widget', 'finished',
            'error', 'running', 'interaction_waiting', 'description', 'icon', 'type', 'progress', 'inputs', 'outputs',
            'workflow_link')


class WidgetPositionSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Widget
        fields = ('x', 'y')


class WidgetListSerializer(serializers.HyperlinkedModelSerializer):
    abstract_widget = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Widget
        # exclude = ('abstract_widget',)


class WorkflowSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField(read_only=True)
    widgets = WidgetSerializer(many=True, read_only=True)
    user = UserSerializer(read_only=True)
    connections = ConnectionSerializer(many=True, read_only=True)
    is_subprocess = serializers.SerializerMethodField()
    is_public = serializers.BooleanField(source='public')

    def get_is_subprocess(self, obj):
        if obj.widget == None:
            return False
        else:
            return True

    class Meta:
        model = Workflow
        exclude = ('public',)
