import React from 'react';
import { Banknote, CircleDollarSign, PiggyBank, Receipt } from 'lucide-react';
import {
  cn,
  fieldErrorClass,
  fieldLabelClass,
  formatCurrency,
  inputClass,
  statCardClass,
  textareaClass,
} from './theme';
import { StepProps } from './types';

const infoCards = [
  { title: 'Lucro Estimado', icon: CircleDollarSign },
  { title: 'Economia do Cliente', icon: PiggyBank },
];

function ReadOnlyField({ label, value }: { label: string; value: string }) {
  return (
    <div className='space-y-2'>
      <label className={fieldLabelClass}>{label}</label>
      <input className={`${inputClass} bg-[#172233] text-[#99a1af]`} value={value} disabled />
    </div>
  );
}

export const StepValores: React.FC<StepProps> = ({ data, errors, onUpdate }) => {
  const valores = data.valores;
  const update = (patch: Partial<typeof valores>) => onUpdate({ valores: { ...valores, ...patch } });

  return (
    <div className='space-y-6'>
      <div className='space-y-2'>
        <h2 className='text-[24px] font-semibold leading-8 text-white'>Valores</h2>
        <p className='text-base text-[#99a1af]'>Feche custos, referência e margem antes da revisão final</p>
      </div>

      <section className='rounded-[12px] border border-[#364153] bg-[#101828] p-5'>
        <div className='mb-5 flex items-center gap-3'>
          <span className='flex h-10 w-10 items-center justify-center rounded-[10px] bg-[#1e2939] text-[#99a1af]'>
            <Banknote size={18} />
          </span>
          <div>
            <h3 className='text-lg font-medium text-white'>Custos Operacionais</h3>
            <p className='text-sm text-[#6a7282]'>Base para calcular valor de milheiros e custo final.</p>
          </div>
        </div>

        <div className='grid gap-4 md:grid-cols-2'>
          <div className='space-y-2'>
            <label className={fieldLabelClass}>Quantidade de Milhas</label>
            <input
              className={cn(inputClass, errors.quantidadeMilhas && 'border-[#ef4444]')}
              type='number'
              value={valores.quantidadeMilhas || ''}
              onChange={(e) => update({ quantidadeMilhas: Number(e.target.value) })}
            />
          </div>

          <div className='space-y-2'>
            <label className={fieldLabelClass}>Custo por Milheiro</label>
            <input
              className={cn(inputClass, errors.custoMilhas && 'border-[#ef4444]')}
              type='number'
              step='0.01'
              value={valores.custoMilhas || ''}
              onChange={(e) => update({ custoMilhas: Number(e.target.value) })}
            />
          </div>

          <div className='space-y-2'>
            <label className={fieldLabelClass}>Taxas</label>
            <input
              className={cn(inputClass, errors.taxas && 'border-[#ef4444]')}
              type='number'
              step='0.01'
              value={valores.taxas || ''}
              onChange={(e) => update({ taxas: Number(e.target.value) })}
            />
          </div>

          <ReadOnlyField label='Valor dos Milheiros' value={formatCurrency(valores.valorMilheiros)} />
        </div>
      </section>

      <section className='rounded-[12px] border border-[#364153] bg-[#101828] p-5'>
        <div className='mb-5 flex items-center gap-3'>
          <span className='flex h-10 w-10 items-center justify-center rounded-[10px] bg-[#1e2939] text-[#99a1af]'>
            <Receipt size={18} />
          </span>
          <div>
            <h3 className='text-lg font-medium text-white'>Precificação</h3>
            <p className='text-sm text-[#6a7282]'>Defina referência, valor final e informações complementares.</p>
          </div>
        </div>

        <div className='grid gap-4 md:grid-cols-2'>
          <ReadOnlyField label='Valor Final Cliente' value={formatCurrency(valores.valorFinalCliente)} />

          <div className='space-y-2'>
            <label className={fieldLabelClass}>Valor Total Final</label>
            <input
              className={cn(inputClass, errors.valorTotalFinal && 'border-[#ef4444]')}
              type='number'
              step='0.01'
              value={valores.valorTotalFinal || ''}
              onChange={(e) => update({ valorTotalFinal: Number(e.target.value) })}
            />
          </div>

          <div className='space-y-2'>
            <label className={fieldLabelClass}>Valor de Referência</label>
            <input
              className={inputClass}
              type='number'
              step='0.01'
              value={valores.valorReferencia || ''}
              onChange={(e) => update({ valorReferencia: Number(e.target.value) })}
            />
          </div>

          <div className='space-y-2'>
            <label className={fieldLabelClass}>Localizador</label>
            <input
              className={cn(inputClass, errors.localizador && 'border-[#ef4444]')}
              maxLength={6}
              value={data.localizador}
              onChange={(e) => onUpdate({ localizador: e.target.value.toUpperCase() })}
            />
          </div>
        </div>

        <div className='mt-4 space-y-2'>
          <label className={fieldLabelClass}>Observações</label>
          <textarea
            className={textareaClass}
            rows={4}
            value={data.observacoes}
            onChange={(e) => onUpdate({ observacoes: e.target.value })}
          />
        </div>
      </section>

      <div className='grid gap-4 md:grid-cols-2'>
        {infoCards.map((card, index) => {
          const Icon = card.icon;
          const value = index === 0 ? valores.lucro : valores.economiaObtida;

          return (
            <div key={card.title} className={statCardClass}>
              <div className='flex items-center gap-3'>
                <span className='flex h-10 w-10 items-center justify-center rounded-[10px] bg-[#1e2939] text-[#99a1af]'>
                  <Icon size={18} />
                </span>
                <div>
                  <p className='text-sm text-[#99a1af]'>{card.title}</p>
                  <p className={cn('mt-1 text-[28px] font-semibold', index === 0 ? (value >= 0 ? 'text-[#00c950]' : 'text-[#f87171]') : 'text-[#60a5fa]')}>
                    {formatCurrency(value)}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {(errors.quantidadeMilhas || errors.custoMilhas || errors.taxas || errors.valorTotalFinal || errors.localizador) && (
        <p className={fieldErrorClass}>
          {errors.quantidadeMilhas || errors.custoMilhas || errors.taxas || errors.valorTotalFinal || errors.localizador}
        </p>
      )}
    </div>
  );
};
