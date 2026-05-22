-- ============================================================================
-- SEMAPA - Definición de tablas Cassandra
-- Plataforma Big Data Distribuida para Gestión Inteligente del Consumo de Agua
-- ============================================================================

USE semapa;

-- ============================================================================
-- CATÁLOGOS TERRITORIALES
-- ============================================================================

CREATE TABLE IF NOT EXISTS sub_alcaldias (
    sub_alcaldia_id int PRIMARY KEY,
    nombre text
);

CREATE TABLE IF NOT EXISTS distritos (
    distrito_id int PRIMARY KEY,
    sub_alcaldia_id int,
    nombre text,
    habitantes int
);

CREATE TABLE IF NOT EXISTS zonas (
    distrito_id int,
    zona_id int,
    nombre text,
    gateway_id int,
    PRIMARY KEY ((distrito_id), zona_id)
);

CREATE TABLE IF NOT EXISTS gateways (
    gateway_id int PRIMARY KEY,
    nombre text,
    latitud double,
    longitud double
);

CREATE TABLE IF NOT EXISTS modelos_medidor (
    modelo_id int PRIMARY KEY,
    marca text,
    modelo text,
    conectividad text,
    aplicacion text
);

CREATE TABLE IF NOT EXISTS tarifas (
    categoria text PRIMARY KEY,
    alias text,
    fijo_m3 decimal,
    usd_mes decimal,
    r_13_25 decimal,
    r_26_50 decimal,
    r_51_75 decimal,
    r_76_100 decimal,
    r_101_150 decimal,
    r_mas_151 decimal,
    descripcion text
);

CREATE TABLE IF NOT EXISTS errores_iot (
    codigo int PRIMARY KEY,
    descripcion text
);

CREATE TABLE IF NOT EXISTS tipos_infraestructura (
    tipo_id int PRIMARY KEY,
    descripcion text
);

-- ============================================================================
-- PERSONAS Y CLIENTES
-- ============================================================================

CREATE TABLE IF NOT EXISTS personas (
    persona_id uuid PRIMARY KEY,
    tipo text,
    documento text,
    nombre text,
    apellidos text,
    razon_social text,
    email text,
    telefono text,
    fecha_registro timestamp
);

CREATE TABLE IF NOT EXISTS personas_por_documento (
    documento text PRIMARY KEY,
    persona_id uuid,
    tipo text,
    nombre text,
    apellidos text,
    razon_social text,
    email text,
    telefono text
);

-- ============================================================================
-- INFRAESTRUCTURAS
-- Fuente principal: infraestructuras_cochabamba.csv
-- ============================================================================

CREATE TABLE IF NOT EXISTS infraestructuras (
    infraestructura_id uuid PRIMARY KEY,
    persona_id uuid,
    numero_catastro text,
    propietario text,
    ci text,
    tipo_infra int,
    distrito_id int,
    zona_id int,
    zona_nombre text,
    distrito_nombre text,
    direccion text,
    manzano text,
    lote text,
    superficie_terreno decimal,
    area_construida decimal,
    uso_suelo text,
    matricula_ddrr text,
    valor_catastral decimal,
    impuesto_anual decimal,
    latitud double,
    longitud double
);

CREATE TABLE IF NOT EXISTS infraestructuras_por_catastro (
    numero_catastro text PRIMARY KEY,
    infraestructura_id uuid,
    persona_id uuid,
    propietario text,
    ci text,
    direccion text,
    zona text,
    distrito text,
    distrito_id int,
    zona_id int,
    manzano text,
    lote text,
    superficie_terreno decimal,
    area_construida decimal,
    uso_suelo text,
    matricula_ddrr text,
    valor_catastral decimal,
    impuesto_anual decimal,
    latitud double,
    longitud double
);

CREATE TABLE IF NOT EXISTS infraestructuras_por_zona (
    distrito_id int,
    zona_id int,
    numero_catastro text,
    infraestructura_id uuid,
    propietario text,
    ci text,
    direccion text,
    uso_suelo text,
    latitud double,
    longitud double,
    PRIMARY KEY ((distrito_id, zona_id), numero_catastro)
);

-- ============================================================================
-- CONTRATOS DE AGUA
-- Fuente principal: contratos_agua.csv
-- ============================================================================

CREATE TABLE IF NOT EXISTS contratos (
    numero_contrato bigint PRIMARY KEY,
    numero_catastro text,
    titular_contrato text,
    ci_titular text,
    categoria text,
    subcategoria text,
    medidor_iot text,
    fecha_contrato date,
    estado_contrato text,
    diametro_conexion text,
    tipo_servicio text,
    fecha_carga timestamp
);

CREATE TABLE IF NOT EXISTS contratos_por_ci (
    ci_titular text,
    numero_contrato bigint,
    numero_catastro text,
    titular_contrato text,
    categoria text,
    subcategoria text,
    medidor_iot text,
    estado_contrato text,
    fecha_contrato date,
    PRIMARY KEY ((ci_titular), numero_contrato)
);

CREATE TABLE IF NOT EXISTS contratos_por_catastro (
    numero_catastro text,
    numero_contrato bigint,
    titular_contrato text,
    ci_titular text,
    categoria text,
    subcategoria text,
    medidor_iot text,
    estado_contrato text,
    fecha_contrato date,
    PRIMARY KEY ((numero_catastro), numero_contrato)
);

CREATE TABLE IF NOT EXISTS contratos_por_medidor (
    medidor_iot text,
    numero_contrato bigint,
    numero_catastro text,
    titular_contrato text,
    ci_titular text,
    categoria text,
    subcategoria text,
    estado_contrato text,
    fecha_contrato date,
    PRIMARY KEY ((medidor_iot), numero_contrato)
);

CREATE TABLE IF NOT EXISTS contratos_por_estado (
    estado_contrato text,
    categoria text,
    numero_contrato bigint,
    titular_contrato text,
    ci_titular text,
    numero_catastro text,
    medidor_iot text,
    fecha_contrato date,
    PRIMARY KEY ((estado_contrato, categoria), numero_contrato)
);

-- ============================================================================
-- MEDIDORES IOT
-- Fuente principal: medidores_iot.csv + contratos_agua.csv
-- ============================================================================

CREATE TABLE IF NOT EXISTS medidores (
    medidor_id uuid PRIMARY KEY,
    medidor_iot text,
    mac text,
    numero_serie text,
    numero_contrato bigint,
    numero_catastro text,
    infraestructura_id uuid,
    persona_id uuid,
    modelo_id int,
    tipo_medidor_id int,
    categoria_tarifa text,
    gateway_id int,
    distrito_id int,
    zona_id int,
    latitud double,
    longitud double,
    fecha_instalacion date,
    fecha_desinstalacion date,
    fecha_retiro date,
    estado text,
    motivo_estado text,
    medidor_anterior_id uuid,
    es_medidor_actual boolean
);

CREATE TABLE IF NOT EXISTS medidores_por_iot (
    medidor_iot text PRIMARY KEY,
    medidor_id uuid,
    mac text,
    numero_serie text,
    numero_contrato bigint,
    numero_catastro text,
    modelo_id int,
    tipo_medidor_id int,
    categoria_tarifa text,
    gateway_id int,
    distrito_id int,
    zona_id int,
    latitud double,
    longitud double,
    fecha_instalacion date,
    fecha_desinstalacion date,
    estado text
);

CREATE TABLE IF NOT EXISTS medidores_por_contrato (
    numero_contrato bigint,
    medidor_id uuid,
    medidor_iot text,
    mac text,
    numero_serie text,
    numero_catastro text,
    modelo_id int,
    tipo_medidor_id int,
    categoria_tarifa text,
    gateway_id int,
    distrito_id int,
    zona_id int,
    latitud double,
    longitud double,
    estado text,
    es_medidor_actual boolean,
    PRIMARY KEY ((numero_contrato), medidor_id)
);

CREATE TABLE IF NOT EXISTS medidores_por_mac (
    mac text PRIMARY KEY,
    medidor_id uuid,
    medidor_iot text,
    numero_serie text,
    numero_contrato bigint,
    numero_catastro text,
    modelo_id int,
    tipo_medidor_id int,
    categoria_tarifa text,
    gateway_id int,
    distrito_id int,
    zona_id int,
    estado text
);

CREATE TABLE IF NOT EXISTS medidores_por_serie (
    numero_serie text PRIMARY KEY,
    medidor_id uuid,
    medidor_iot text,
    mac text,
    numero_contrato bigint,
    numero_catastro text,
    modelo_id int,
    tipo_medidor_id int,
    categoria_tarifa text,
    gateway_id int,
    distrito_id int,
    zona_id int,
    estado text
);

CREATE TABLE IF NOT EXISTS medidores_por_estado_zona (
    estado text,
    distrito_id int,
    zona_id int,
    medidor_id uuid,
    medidor_iot text,
    numero_serie text,
    numero_contrato bigint,
    categoria_tarifa text,
    gateway_id int,
    PRIMARY KEY ((estado, distrito_id, zona_id), medidor_id)
);

-- ============================================================================
-- LECTURAS IOT RAW
-- Lecturas crudas tal como llegan desde simulador/ingestor
-- ============================================================================

CREATE TABLE IF NOT EXISTS lecturas_raw (
    gateway_id int,
    fecha date,
    ts timestamp,
    mac text,
    payload text,
    procesado boolean,
    error_motivo text,
    PRIMARY KEY ((gateway_id, fecha), ts, mac)
);

-- ============================================================================
-- LECTURAS POR MEDIDOR
-- Time-series optimizada por medidor y mes
-- ============================================================================

CREATE TABLE IF NOT EXISTS lecturas_por_medidor (
    medidor_id uuid,
    anio_mes int,
    fecha_hora timestamp,
    gateway_id int,
    lectura_litros bigint,
    consumo_litros int,
    status int,
    PRIMARY KEY ((medidor_id, anio_mes), fecha_hora)
) WITH CLUSTERING ORDER BY (fecha_hora DESC)
  AND compression = {'class': 'LZ4Compressor'}
  AND compaction = {
      'class': 'TimeWindowCompactionStrategy',
      'compaction_window_unit': 'DAYS',
      'compaction_window_size': '7'
  };

-- ============================================================================
-- LECTURAS POR ZONA, DÍA Y HORA
-- Vista denormalizada para dashboards territoriales
-- ============================================================================

CREATE TABLE IF NOT EXISTS lecturas_por_zona_dia (
    distrito_id int,
    zona_id int,
    fecha date,
    hora int,
    medidor_id uuid,
    consumo_litros int,
    categoria_tarifa text,
    PRIMARY KEY ((distrito_id, zona_id, fecha), hora, medidor_id)
) WITH CLUSTERING ORDER BY (hora ASC, medidor_id ASC);

-- ============================================================================
-- COBERTURA POR GATEWAY
-- Para dashboard de infraestructura inteligente
-- ============================================================================

CREATE TABLE IF NOT EXISTS cobertura_gateway (
    gateway_id int,
    zona_id int,
    medidor_id uuid,
    ultima_lectura timestamp,
    PRIMARY KEY ((gateway_id), zona_id, medidor_id)
);

-- ============================================================================
-- LECTURAS MANUALES
-- App móvil: lectura manual + GPS + fotografía
-- ============================================================================

CREATE TABLE IF NOT EXISTS lecturas_manuales (
    medidor_id uuid,
    fecha_hora timestamp,
    usuario text,
    lectura_litros bigint,
    lat double,
    lon double,
    foto_url text,
    observacion text,
    numero_contrato bigint,
    medidor_iot text,
    estado text,
    PRIMARY KEY ((medidor_id), fecha_hora)
) WITH CLUSTERING ORDER BY (fecha_hora DESC);

CREATE TABLE IF NOT EXISTS lecturas_manuales_por_usuario (
    usuario text,
    fecha_hora timestamp,
    medidor_id uuid,
    numero_contrato bigint,
    medidor_iot text,
    lectura_litros bigint,
    lat double,
    lon double,
    foto_url text,
    estado text,
    PRIMARY KEY ((usuario), fecha_hora, medidor_id)
) WITH CLUSTERING ORDER BY (fecha_hora DESC);

-- ============================================================================
-- FACTURACIÓN
-- ============================================================================

CREATE TABLE IF NOT EXISTS facturas (
    numero_contrato bigint,
    periodo text,
    factura_id uuid,
    medidor_id uuid,
    persona_id uuid,
    consumo_m3 decimal,
    monto_usd decimal,
    monto_bs decimal,
    tipo_cambio decimal,
    categoria_tarifa text,
    desglose text,
    fecha_emision timestamp,
    estado text,
    PRIMARY KEY ((numero_contrato), periodo)
) WITH CLUSTERING ORDER BY (periodo DESC);

CREATE TABLE IF NOT EXISTS facturas_por_periodo (
    periodo text,
    distrito_id int,
    numero_contrato bigint,
    monto_usd decimal,
    monto_bs decimal,
    consumo_m3 decimal,
    categoria_tarifa text,
    estado text,
    fecha_emision timestamp,
    PRIMARY KEY ((periodo, distrito_id), numero_contrato)
);

CREATE TABLE IF NOT EXISTS facturas_por_categoria (
    periodo text,
    categoria_tarifa text,
    numero_contrato bigint,
    monto_bs decimal,
    consumo_m3 decimal,
    estado text,
    PRIMARY KEY ((periodo, categoria_tarifa), numero_contrato)
);

-- ============================================================================
-- PREAVISOS
-- Entregable 2: mensajería asincrónica
-- Entregable 3: PDFs rollo térmico y media carta
-- ============================================================================

CREATE TABLE IF NOT EXISTS preavisos_por_periodo (
    periodo text,
    canal text,
    preaviso_id uuid,
    numero_contrato bigint,
    ci_titular text,
    titular_contrato text,
    destino text,
    medidor_iot text,
    consumo_m3 decimal,
    monto_bs decimal,
    categoria_tarifa text,
    estado text,
    proveedor text,
    proveedor_message_id text,
    pdf_media_carta_url text,
    pdf_rollo_url text,
    fecha_creacion timestamp,
    fecha_envio timestamp,
    fecha_entrega timestamp,
    error text,
    PRIMARY KEY ((periodo), canal, preaviso_id)
);

CREATE TABLE IF NOT EXISTS preavisos_por_contrato (
    numero_contrato bigint,
    periodo text,
    canal text,
    preaviso_id uuid,
    titular_contrato text,
    destino text,
    consumo_m3 decimal,
    monto_bs decimal,
    estado text,
    proveedor text,
    proveedor_message_id text,
    fecha_creacion timestamp,
    fecha_envio timestamp,
    error text,
    PRIMARY KEY ((numero_contrato), periodo, canal, preaviso_id)
);

CREATE TABLE IF NOT EXISTS eventos_mensajeria (
    preaviso_id uuid,
    fecha_evento timestamp,
    canal text,
    estado text,
    detalle text,
    proveedor text,
    proveedor_message_id text,
    error text,
    PRIMARY KEY ((preaviso_id), fecha_evento)
) WITH CLUSTERING ORDER BY (fecha_evento DESC);

-- ============================================================================
-- PDFS DE PREAVISO
-- ============================================================================

CREATE TABLE IF NOT EXISTS pdfs_preaviso (
    preaviso_id uuid,
    formato text,
    numero_contrato bigint,
    periodo text,
    archivo_url text,
    qr_validacion text,
    hash_archivo text,
    fecha_generacion timestamp,
    PRIMARY KEY ((preaviso_id), formato)
);

-- ============================================================================
-- TÓTEM / KIOSCO DE AUTOSERVICIO
-- ============================================================================

CREATE TABLE IF NOT EXISTS kiosk_consultas (
    kiosk_id text,
    fecha_hora timestamp,
    tipo_consulta text,
    numero_contrato bigint,
    ci_titular text,
    resultado text,
    estado text,
    PRIMARY KEY ((kiosk_id), fecha_hora)
) WITH CLUSTERING ORDER BY (fecha_hora DESC);

CREATE TABLE IF NOT EXISTS reclamos_ciudadanos (
    reclamo_id uuid PRIMARY KEY,
    numero_contrato bigint,
    ci_titular text,
    titular_contrato text,
    tipo_reclamo text,
    descripcion text,
    latitud double,
    longitud double,
    estado text,
    fecha_creacion timestamp,
    fecha_actualizacion timestamp
);

CREATE TABLE IF NOT EXISTS reclamos_por_contrato (
    numero_contrato bigint,
    fecha_creacion timestamp,
    reclamo_id uuid,
    tipo_reclamo text,
    descripcion text,
    estado text,
    PRIMARY KEY ((numero_contrato), fecha_creacion, reclamo_id)
) WITH CLUSTERING ORDER BY (fecha_creacion DESC);

-- ============================================================================
-- RESÚMENES PARA DASHBOARD ALCALDÍA
-- Smart City / ODS / Cobertura / Impacto social
-- ============================================================================

CREATE TABLE IF NOT EXISTS resumen_dashboard_alcaldia (
    periodo text,
    distrito_id int,
    zona_id int,
    poblacion_beneficiaria int,
    medidores_totales int,
    medidores_activos int,
    sensores_con_fallas int,
    consumo_total_m3 decimal,
    consumo_per_capita_litros decimal,
    cobertura_servicio decimal,
    zonas_criticas int,
    fecha_actualizacion timestamp,
    PRIMARY KEY ((periodo), distrito_id, zona_id)
);

-- ============================================================================
-- RESÚMENES PARA DASHBOARD GERENCIA
-- Operación / mantenimiento / consumo / anomalías
-- ============================================================================

CREATE TABLE IF NOT EXISTS resumen_dashboard_gerencia (
    periodo text,
    distrito_id int,
    zona_id int,
    consumo_total_m3 decimal,
    consumo_promedio_diario_m3 decimal,
    pico_maximo_horario_m3 decimal,
    medidores_activos int,
    medidores_inactivos int,
    medidores_fuera_servicio int,
    medidores_con_error int,
    lecturas_faltantes int,
    lecturas_app_movil int,
    latencia_ingestion_ms decimal,
    fecha_actualizacion timestamp,
    PRIMARY KEY ((periodo), distrito_id, zona_id)
);

-- ============================================================================
-- RESÚMENES PARA DASHBOARD CONTABILIDAD
-- Facturación / recaudación / mora / preavisos
-- ============================================================================

CREATE TABLE IF NOT EXISTS resumen_dashboard_contabilidad (
    periodo text,
    distrito_id int,
    categoria_tarifa text,
    monto_facturado_bs decimal,
    monto_recaudado_bs decimal,
    cartera_vencida_bs decimal,
    contratos_activos int,
    contratos_morosos int,
    preavisos_emitidos int,
    preavisos_entregados int,
    preavisos_fallidos int,
    ticket_promedio_bs decimal,
    fecha_actualizacion timestamp,
    PRIMARY KEY ((periodo), distrito_id, categoria_tarifa)
);

-- ============================================================================
-- PROYECCIONES FINANCIERAS Y DEMANDA
-- ============================================================================

CREATE TABLE IF NOT EXISTS proyeccion_ingresos_por_categoria (
    periodo text,
    categoria_tarifa text,
    consumo_m3 decimal,
    ingresos_estimados_bs decimal,
    ingresos_estimados_usd decimal,
    contratos int,
    fecha_calculo timestamp,
    PRIMARY KEY ((periodo), categoria_tarifa)
);

CREATE TABLE IF NOT EXISTS proyeccion_demanda_por_distrito (
    distrito_id int,
    anio int,
    consumo_proyectado_m3 decimal,
    factor_crecimiento decimal,
    poblacion_estimada int,
    fecha_calculo timestamp,
    PRIMARY KEY ((distrito_id), anio)
);

-- ============================================================================
-- AUTENTICACIÓN Y USUARIOS DEL SISTEMA
-- ============================================================================

CREATE TABLE IF NOT EXISTS usuarios_sistema (
    username text PRIMARY KEY,
    password_hash text,
    rol text,
    nombre text,
    email text,
    activo boolean,
    fecha_creacion timestamp,
    ultimo_acceso timestamp
);