{%- if not replace %}
CREATE TABLE IF NOT EXISTS {{ full_name }}
{%- elif replace and can_replace_table %}
CREATE OR REPLACE TABLE {{ full_name }}
{%- elif replace and not can_replace_table %}
{% if table_exists %}
DROP TABLE IF EXISTS {{ full_name }}{{ ' CASCADE' if needs_cascade else ''}};
{% elif view_exists %}
DROP VIEW IF EXISTS {{ full_name }}{{ ' CASCADE' if needs_cascade else ''}};
{% endif %}

CREATE TABLE {{ full_name }}
{%- else %}
CREATE TABLE
{%- endif %}

{%- if columns is defined and columns|length > 0 %}
(
{%- for col_def in columns %}
    {{ col_def['name'] }} {{ col_def['type'] }}
    {{- ' PRIMARY KEY' if col_def.get('primary')}}
    {{- ' UNIQUE' if col_def.get('unique')}}
    {{- ' NOT NULL' if col_def.get('unique')}}
    {{- ',' if not loop.last else ''}}
{%- endfor %}
)
{%- endif %}

{%- block table_attributes %}
{%- if partition is defined %}
PARTITION BY {{ partition }}
{% endif %}

{%- if cluster is defined %}
CLUSTER BY ({{ ', '.join(cluster) }}}
{% endif %}

{%- if distribution is defined %}
DISTSTYLE {{ distribution['style'] }}
{% if distribution['style'] == 'key' %}DISTKEY({{ distribution['key'] }}){% endif %}
{% endif %}

{%- if sorting is defined %}
{{ sorting['type']+' ' if 'type' in sorting else '' }}SORTKEY({{ ', '.join(sorting['columns']) }})
{% endif %}
{% endblock -%}

{%- if select is defined %}
{%- if not can_specify_ddl_select and columns is defined and columns|length > 0 %}
;

INSERT INTO {{ full_name }}
{% else %}
AS
{% endif %}
  {%- if columns is defined and columns|length > 0 %}
SELECT {{ columns|join('\n     , ', attribute='name') }}
  FROM ({{ select }}) t
  {%- else %}
{{ select }}
  {%- endif %}
{% endif -%}
;

{% block indexes %}
{% if indexes is defined %}
  {% for name, idx_def in indexes.items() %}
CREATE INDEX {{ table_name }}_{{ name }} ON {{ full_name }}({{ ', '.join(idx_def['columns']) }});
  {% endfor %}
{% endif %}
{% endblock %}

{% block permissions %}
{% if permissions is defined %}
  {% for role, priv in permissions.items() %}
GRANT {{ priv }} ON {{ full_name }} TO {{ role }};
  {% endfor %}
{% endif %}
{% endblock %}
