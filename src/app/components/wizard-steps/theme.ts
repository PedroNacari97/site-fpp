import { EmissionData, Option, StepId, TipoEmissao, TipoPassageiro } from './types';

export interface StepMeta {
  id: StepId;
  title: string;
  subtitle: string;
}

export interface ProgramOption extends Option {
  iconBackground: string;
  textAccent: string;
}

export const EMISSION_TYPES: Array<Option & { iconTone: string }> = [
  {
    id: 'conta_cliente',
    label: 'Conta do Cliente',
    description: 'Cliente usa suas próprias milhas',
    iconTone: 'text-slate-300',
  },
  {
    id: 'conta_administradora',
    label: 'Conta Administradora',
    description: 'Usar milhas da empresa',
    iconTone: 'text-slate-300',
  },
  {
    id: 'emissor_parceiro',
    label: 'Emissor Parceiro',
    description: 'Emissão por terceiros',
    iconTone: 'text-slate-300',
  },
];

export const PROGRAM_OPTIONS: ProgramOption[] = [
  { id: 'latam', label: 'LATAM Pass', iconBackground: 'bg-[#fb2c36]', textAccent: 'text-[#d1d5dc]' },
  { id: 'smiles', label: 'Smiles', iconBackground: 'bg-[#ff6900]', textAccent: 'text-[#d1d5dc]' },
  { id: 'azul', label: 'TudoAzul', iconBackground: 'bg-[#2b7fff]', textAccent: 'text-[#d1d5dc]' },
  { id: 'privilege', label: 'Privilege Club', iconBackground: 'bg-[#a855f7]', textAccent: 'text-[#d1d5dc]' },
];

export const CLIENT_OPTIONS: Option[] = [
  { id: '1', label: 'João Silva • CPF 123.456.789-00' },
  { id: '2', label: 'Maria Souza • CPF 987.654.321-00' },
];

export const WIZARD_STEPS: StepMeta[] = [
  { id: 1, title: 'Cliente & Programa', subtitle: 'Informações do cliente' },
  { id: 2, title: 'Voo de Ida', subtitle: 'Detalhes do voo principal' },
  { id: 3, title: 'Voo de Volta', subtitle: 'Retorno (se aplicável)' },
  { id: 4, title: 'Passageiros', subtitle: 'Dados dos viajantes' },
  { id: 5, title: 'Valores', subtitle: 'Financeiro e custos' },
  { id: 6, title: 'Revisão', subtitle: 'Conferir e finalizar' },
];

export const passengerTypeLabels: Record<TipoPassageiro, string> = {
  adulto: 'Adulto',
  crianca: 'Criança',
  bebe: 'Bebê',
};

export const pageShellClass =
  'min-h-screen bg-[#101828] px-4 py-6 text-white sm:px-6 lg:px-8';
export const headerTitleClass =
  'text-[32px] font-semibold leading-[1.1] tracking-[-0.02em] text-white';
export const headerDescriptionClass = 'text-base text-[#99a1af]';
export const surfaceCardClass =
  'rounded-[14px] border border-[#364153] bg-[#1e2939] shadow-[0_0_0_1px_rgba(16,24,40,0.12)]';
export const innerPanelClass = 'rounded-[10px] border border-[#364153] bg-[#101828]';
export const fieldLabelClass = 'text-sm font-medium text-[#d1d5dc]';
export const fieldHintClass = 'text-xs leading-4 text-[#6a7282]';
export const fieldErrorClass = 'text-xs leading-4 text-[#f87171]';
export const inputClass =
  'h-12 w-full rounded-[10px] border border-[#364153] bg-[#101828] px-4 text-sm text-white outline-none transition focus:border-[#155dfc] focus:ring-2 focus:ring-[#155dfc]/30 placeholder:text-[#6a7282]';
export const textareaClass =
  'w-full rounded-[10px] border border-[#364153] bg-[#101828] px-4 py-3 text-sm text-white outline-none transition focus:border-[#155dfc] focus:ring-2 focus:ring-[#155dfc]/30 placeholder:text-[#6a7282]';
export const selectClass = `${inputClass} appearance-none pr-10`;
export const primaryButtonClass =
  'inline-flex h-12 items-center justify-center gap-2 rounded-[10px] bg-[#155dfc] px-5 text-sm font-medium text-white transition hover:bg-[#0f4ee8] disabled:cursor-not-allowed disabled:opacity-60';
export const secondaryButtonClass =
  'inline-flex h-12 items-center justify-center gap-2 rounded-[10px] border border-[#364153] bg-[#101828] px-5 text-sm font-medium text-[#d1d5dc] transition hover:border-[#4a5565] hover:text-white disabled:cursor-not-allowed disabled:opacity-50';
export const tertiaryButtonClass =
  'inline-flex h-10 items-center justify-center gap-2 rounded-[10px] border border-[#364153] bg-transparent px-4 text-sm font-medium text-[#99a1af] transition hover:border-[#4a5565] hover:text-white';
export const statCardClass =
  'rounded-[12px] border border-[#364153] bg-[#101828] p-4';

export function cn(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(' ');
}

export function getEmissionTypeLabel(tipo: TipoEmissao) {
  return EMISSION_TYPES.find((item) => item.id === tipo)?.label || '-';
}

export function getProgramLabel(programaId: string) {
  return PROGRAM_OPTIONS.find((item) => item.id === programaId)?.label || '-';
}

export function getClientLabel(clienteId: string) {
  return CLIENT_OPTIONS.find((item) => item.id === clienteId)?.label || 'Cliente #-';
}

export function formatCurrency(value: number) {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 2,
  }).format(Number.isFinite(value) ? value : 0);
}

export function formatDateTime(value: string) {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(parsed);
}

export function getPassengerSummary(data: EmissionData) {
  const total = data.passageiros.length;
  const byType = data.passageiros.reduce<Record<TipoPassageiro, number>>(
    (acc, passenger) => {
      acc[passenger.tipo] += 1;
      return acc;
    },
    { adulto: 0, crianca: 0, bebe: 0 },
  );

  return {
    total,
    byType,
    label:
      total > 0
        ? `${byType.adulto} adulto(s), ${byType.crianca} criança(s) e ${byType.bebe} bebê(s)`
        : 'Nenhum passageiro adicionado',
  };
}
