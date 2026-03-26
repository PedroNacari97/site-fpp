export type StepId = 1 | 2 | 3 | 4 | 5 | 6;

export type TipoEmissao = 'conta_cliente' | 'conta_administradora' | 'emissor_parceiro' | '';
export type TipoPassageiro = 'adulto' | 'crianca' | 'bebe';

export interface EscalaData {
  id: string;
  iata: string;
  companhia: string;
  horario: string;
}

export interface VooData {
  origem: string;
  destino: string;
  companhia: string;
  dataHora: string;
  possuiEscala: boolean;
  escalas: EscalaData[];
}

export interface PassageiroData {
  id: string;
  tipo: TipoPassageiro;
  nome: string;
  cpf: string;
  rg?: string;
  passaporte?: string;
  validadePassaporte?: string;
  dataNascimento: string;
  observacoes?: string;
}

export interface ValoresData {
  quantidadeMilhas: number;
  custoMilhas: number;
  taxas: number;
  valorMilheiros: number;
  valorFinalCliente: number;
  valorTotalFinal: number;
  lucro: number;
  margemPercentual: number;
  valorReferencia: number;
  economiaObtida: number;
  economiaPercentual: number;
}

export interface EmissionData {
  tipoEmissao: TipoEmissao;
  clienteId: string;
  programaId: string;
  vooIda: VooData;
  possuiVolta: boolean;
  vooVolta: VooData;
  passageiros: PassageiroData[];
  valores: ValoresData;
  localizador: string;
  observacoes: string;
}

export interface ValidationErrors {
  [key: string]: string;
}

export interface Option {
  id: string;
  label: string;
  description?: string;
  color?: string;
}

export interface StepProps {
  data: EmissionData;
  errors: ValidationErrors;
  onUpdate: (patch: Partial<EmissionData>) => void;
}
