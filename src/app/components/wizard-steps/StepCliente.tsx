import React from 'react';
import { Box, Building2, ChevronDown, FileText, Handshake, UserRound } from 'lucide-react';
import {
  CLIENT_OPTIONS,
  cn,
  EMISSION_TYPES,
  fieldErrorClass,
  fieldHintClass,
  fieldLabelClass,
  getClientLabel,
  inputClass,
  PROGRAM_OPTIONS,
} from './theme';
import { StepProps, TipoEmissao } from './types';

const typeIcons = {
  conta_cliente: FileText,
  conta_administradora: Building2,
  emissor_parceiro: Handshake,
};

export const StepCliente: React.FC<StepProps> = ({ data, errors, onUpdate }) => {
  return (
    <div className='space-y-6'>
      <div className='space-y-2'>
        <h2 className='text-[24px] font-semibold leading-8 text-white'>Dados do Cliente</h2>
        <p className='text-base text-[#99a1af]'>Selecione o cliente e o tipo de emissão</p>
      </div>

      <section className='space-y-3'>
        <label className={fieldLabelClass}>Tipo de Emissão *</label>
        <div className='grid gap-4 lg:grid-cols-3'>
          {EMISSION_TYPES.map((tipo) => {
            const Icon = typeIcons[tipo.id as keyof typeof typeIcons];
            const selected = data.tipoEmissao === tipo.id;

            return (
              <button
                key={tipo.id}
                type='button'
                onClick={() => onUpdate({ tipoEmissao: tipo.id as TipoEmissao })}
                className={cn(
                  'rounded-[10px] border bg-[#101828] p-4 text-left transition',
                  selected
                    ? 'border-[#155dfc] shadow-[0_0_0_2px_rgba(21,93,252,0.16)]'
                    : 'border-[#364153] hover:border-[#4a5565]',
                )}
              >
                <div className='flex items-start gap-3'>
                  <span className='mt-1 text-[#99a1af]'>
                    <Icon size={18} />
                  </span>
                  <div className='space-y-1'>
                    <p className='text-base font-medium text-[#d1d5dc]'>{tipo.label}</p>
                    <p className='text-xs leading-4 text-[#6a7282]'>{tipo.description}</p>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
        {errors.tipoEmissao && <p className={fieldErrorClass}>{errors.tipoEmissao}</p>}
      </section>

      <section className='space-y-2'>
        <label className={fieldLabelClass}>Cliente *</label>
        <div className='relative'>
          <UserRound className='pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#6a7282]' size={18} />
          <select
            className={`${inputClass} appearance-none pl-11 pr-12`}
            value={data.clienteId}
            onChange={(e) => onUpdate({ clienteId: e.target.value })}
          >
            <option value=''>Selecione um cliente</option>
            {CLIENT_OPTIONS.map((cliente) => (
              <option key={cliente.id} value={cliente.id}>
                {cliente.label}
              </option>
            ))}
          </select>
          <ChevronDown className='pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-[#6a7282]' size={18} />
        </div>
        <p className={fieldHintClass}>
          Ao selecionar um cliente, você pode reaproveitar passageiros frequentes
        </p>
        {errors.clienteId && <p className={fieldErrorClass}>{errors.clienteId}</p>}
      </section>

      <section className='space-y-3'>
        <label className={fieldLabelClass}>Programa de Milhas *</label>
        <div className='grid gap-4 sm:grid-cols-2 xl:grid-cols-4'>
          {PROGRAM_OPTIONS.map((programa) => {
            const selected = data.programaId === programa.id;

            return (
              <button
                key={programa.id}
                type='button'
                onClick={() => onUpdate({ programaId: programa.id })}
                aria-label={programa.label}
                className={cn(
                  'rounded-[10px] border bg-[#101828] px-4 py-5 transition',
                  selected
                    ? 'border-[#155dfc] shadow-[0_0_0_2px_rgba(21,93,252,0.16)]'
                    : 'border-[#364153] hover:border-[#4a5565]',
                )}
              >
                <div className='flex flex-col items-center gap-3'>
                  <span className={cn('flex h-10 w-10 items-center justify-center rounded-[10px] text-white', programa.iconBackground)}>
                    <Box size={18} />
                  </span>
                  <span className={cn('text-sm font-medium', selected ? 'text-white' : programa.textAccent)}>{programa.label}</span>
                </div>
              </button>
            );
          })}
        </div>
        {errors.programaId && <p className={fieldErrorClass}>{errors.programaId}</p>}
      </section>

      {(data.clienteId || data.programaId) && (
        <div className='rounded-[12px] border border-[#364153] bg-[#101828] px-4 py-3 text-sm text-[#99a1af]'>
          <span className='text-white'>{getClientLabel(data.clienteId)}</span>
          {' • '}
          <span className='text-white'>{PROGRAM_OPTIONS.find((item) => item.id === data.programaId)?.label || 'Sem programa selecionado'}</span>
        </div>
      )}
    </div>
  );
};
