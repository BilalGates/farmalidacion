/** Etiquetas de presentación; nunca transforman códigos ni valores de origen. */
const LABELS: Record<string, string> = {
  DESCRIPCION: 'Descripción', ME_DESCRIPCION: 'Descripción del medicamento',
  EX_DESCRIPCION: 'Descripción', NOMBRE: 'Nombre', CODIGO_NACIONAL: 'Código nacional',
  REPOSICION: 'Reposición', SW_USO_HOSPITALARIO: 'Uso hospitalario',
  TEV_CODIGO: 'Tipo de envase', TEV_IDEXTERNO: 'Identificador externo de envase',
  VERIFICAR_DISPENSACION_AMBULATORIA: 'Verificar dispensación ambulatoria',
  VALIDAR_NHC_ICU_IMPUTACION: 'Validar imputación NHC/ICU',
  CANTIDAD: 'Cantidad', ATC: 'Código ATC', DISPENSAR: 'Dispensar',
  DESCRIPCION_GESTION: 'Descripción de gestión', PERMITE_COMPRAR: 'Permite comprar',
  BN_IDEXTERNO: 'Identificador externo (BN)',
  ACTIVO: 'Activo', ALTID_PRESCRIPCION: 'Identificador alternativo de prescripción',
  COMPARTIBLE: 'Compartible', CONSUMIR_HASTA_AGOTAR: 'Consumir hasta agotar',
  CONTROL: 'Control', COPAGO: 'Copago', DESCRIPCION_PRESCRIPCION: 'Descripción de prescripción',
  DESCUENTO: 'Descuento', DESCUENTO_PROVEEDOR: 'Descuento del proveedor',
  DISPONIBLE_AMBULATORIO: 'Disponible en ambulatorio',
  DISPONIBLE_FORMULA_MAGISTRAL: 'Disponible en fórmula magistral',
  DISPONIBLE_HDIA: 'Disponible (HDIA)', DISPONIBLE_INGRESO: 'Disponible en ingreso',
  DISPONIBLE_IRMP: 'Disponible (IRMP)', DISPONIBLE_MIV: 'Disponible (MIV)',
  DISPONIBLE_PEDIDO_PLANTA: 'Disponible en pedido de planta',
  DISPONIBLE_PRESCRIPCION_LIBRE_HDIA: 'Disponible en prescripción libre (HDIA)',
  EAN13_COMPRA: 'EAN13 de compra', ENSAYO_CLINICO: 'Ensayo clínico', EN_GUIA: 'En guía',
  EXTRANJERO: 'Extranjero', FACTORCOMPRA: 'Factor de compra', FACTORSUMINISTRO: 'Factor de suministro',
  FRACCION_AMBULATORIO: 'Fracción en ambulatorio', FRACCION_INGRESO: 'Fracción en ingreso',
  GESTIONAR_PEDIDOS_POR: 'Gestionar pedidos por', ME_ALTID: 'Identificador alternativo del medicamento',
  ME_IDEXTERNO: 'Identificador externo del medicamento', EX_IDEXTERNO: 'Identificador externo (EX)',
  MULTIDOSIS: 'Multidosis', MULTIPLO_DISPENSACION_AMBULATORIO: 'Múltiplo de dispensación ambulatoria',
  MULTIPLO_DISPENSACION_HDIA: 'Múltiplo de dispensación (HDIA)',
  PERMITE_COMPRA_CENTRALIZADA: 'Permite compra centralizada', PERMITE_CONSUMOS: 'Permite consumos',
  PERMITE_FABRICAR: 'Permite fabricar', PERMITE_PEDIDOS_SINCONCURSO: 'Permite pedidos sin concurso',
  PR_CODIGO: 'Código (PR)', PR_IDEXTERNO: 'Identificador externo (PR)',
}
const BLOCK_LABELS: Record<string, string> = {
  specialty_general: 'Datos generales de especialidad', specialty_excipient: 'Excipientes',
  medication_general: 'Datos generales de medicamento', active_ingredient_general: 'Datos generales de principio activo',
}
export function blockLabel(code: string): string { return BLOCK_LABELS[code] ?? code }
export function fieldLabel(code: string): string { return LABELS[code] ?? code }
export function searchText(text: string): string {
  return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es')
}
