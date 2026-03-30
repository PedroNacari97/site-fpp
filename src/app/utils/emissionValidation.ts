import { EmissionData, PassageiroData, StepId, ValidationErrors } from '../components/wizard-steps/types';

const IATA_REGEX = /^[A-Z]{3}$/;

export const normalizeIata = (value: string) => value.toUpperCase().replace(/[^A-Z]/g, '').slice(0, 3);

export function isFutureDate(value: string): boolean {
  if (!value) return false;
  const date = new Date(value);
  return Number.isFinite(date.getTime()) && date.getTime() > Date.now();
}

export function isValidCPF(cpf: string): boolean {
  const clean = cpf.replace(/\D/g, '');
  if (clean.length !== 11 || /^(\d)\1+$/.test(clean)) return false;

  const calcDigit = (base: string, factor: number) => {
    let total = 0;
    for (const num of base) {
      total += Number(num) * factor;
      factor -= 1;
    }
    const remainder = (total * 10) % 11;
    return remainder === 10 ? 0 : remainder;
  };

  const digit1 = calcDigit(clean.slice(0, 9), 10);
  const digit2 = calcDigit(clean.slice(0, 10), 11);
  return digit1 === Number(clean[9]) && digit2 === Number(clean[10]);
}

export function getAge(dateISO: string): number {
  if (!dateISO) return 0;
  const birth = new Date(dateISO);
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const month = today.getMonth() - birth.getMonth();
  if (month < 0 || (month === 0 && today.getDate() < birth.getDate())) age -= 1;
  return age;
}

function validatePassengerByType(p: PassageiroData): string | null {
  const age = getAge(p.dataNascimento);
  if (p.tipo === 'adulto' && age < 12) return 'Adulto deve ter ao menos 12 anos';
  if (p.tipo === 'crianca' && (age < 2 || age >= 12)) return 'Criança deve ter entre 2 e 11 anos';
  if (p.tipo === 'bebe' && age >= 2) return 'Bebê deve ter menos de 2 anos';
  return null;
}

export function validateStep(data: EmissionData, step: StepId): ValidationErrors {
  const errors: ValidationErrors = {};

  if (step === 1) {
    if (!data.tipoEmissao) errors.tipoEmissao = 'Selecione o tipo de emissão';
    if (!data.clienteId) errors.clienteId = 'Selecione o cliente';
    if (!data.programaId) errors.programaId = 'Selecione o programa';
  }

  if (step === 2) {
    if (!IATA_REGEX.test(data.vooIda.origem)) errors.vooIdaOrigem = 'Origem deve ter 3 letras';
    if (!IATA_REGEX.test(data.vooIda.destino)) errors.vooIdaDestino = 'Destino deve ter 3 letras';
    if (data.vooIda.origem && data.vooIda.origem === data.vooIda.destino) errors.vooIdaRota = 'Origem e destino devem ser diferentes';
    if (!data.vooIda.companhia) errors.vooIdaCompanhia = 'Companhia é obrigatória';
    if (!isFutureDate(data.vooIda.dataHora)) errors.vooIdaDataHora = 'Data da ida deve ser futura';
    data.vooIda.escalas.forEach((escala, idx) => {
      if (!IATA_REGEX.test(escala.iata) || !escala.companhia || !escala.horario) {
        errors[`vooIdaEscala-${idx}`] = 'Complete os dados da escala';
      }
    });
  }

  if (step === 3 && data.possuiVolta) {
    if (!IATA_REGEX.test(data.vooVolta.origem)) errors.vooVoltaOrigem = 'Origem deve ter 3 letras';
    if (!IATA_REGEX.test(data.vooVolta.destino)) errors.vooVoltaDestino = 'Destino deve ter 3 letras';
    if (data.vooVolta.origem && data.vooVolta.origem === data.vooVolta.destino) errors.vooVoltaRota = 'Origem e destino devem ser diferentes';
    if (!data.vooVolta.companhia) errors.vooVoltaCompanhia = 'Companhia é obrigatória';
    if (!isFutureDate(data.vooVolta.dataHora)) errors.vooVoltaDataHora = 'Data da volta deve ser futura';
  }

  if (step === 4) {
    if (!data.passageiros.length) errors.passageiros = 'Adicione ao menos um passageiro';
    data.passageiros.forEach((p, idx) => {
      if (!p.nome) errors[`passageiroNome-${idx}`] = 'Nome obrigatório';
      if (!isValidCPF(p.cpf)) errors[`passageiroCpf-${idx}`] = 'CPF inválido';
      if (!p.dataNascimento) errors[`passageiroNascimento-${idx}`] = 'Data de nascimento obrigatória';
      const ageError = validatePassengerByType(p);
      if (ageError) errors[`passageiroTipo-${idx}`] = ageError;
    });
  }

  if (step === 5) {
    if (data.valores.quantidadeMilhas <= 0) errors.quantidadeMilhas = 'Milhas deve ser maior que zero';
    if (data.valores.custoMilhas <= 0) errors.custoMilhas = 'Custo do milheiro deve ser maior que zero';
    if (data.valores.taxas < 0) errors.taxas = 'Taxas não pode ser negativo';
    if (data.valores.valorTotalFinal <= 0) errors.valorTotalFinal = 'Valor total final deve ser maior que zero';
    if (data.localizador && data.localizador.length !== 6) errors.localizador = 'Localizador deve ter 6 caracteres';
  }

  return errors;
}

export function validateAll(data: EmissionData): ValidationErrors {
  return [1, 2, 3, 4, 5].reduce<ValidationErrors>((acc, step) => ({ ...acc, ...validateStep(data, step as StepId) }), {});
}
