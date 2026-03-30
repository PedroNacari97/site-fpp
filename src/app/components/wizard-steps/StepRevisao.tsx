import React from 'react';
import { CheckCircle2, Pencil } from 'lucide-react';
import {
  formatCurrency,
  formatDateTime,
  getClientLabel,
  getEmissionTypeLabel,
  getPassengerSummary,
  getProgramLabel,
  statCardClass,
  tertiaryButtonClass,
} from './theme';
import { EmissionData } from './types';

interface Props {
  data: EmissionData;
  onEdit: (step: number) => void;
}

function ReviewGrid({
  items,
}: {
  items: Array<{ label: string; value: string }>;
}) {
  return (
    <div className='grid gap-4 md:grid-cols-2 xl:grid-cols-4'>
      {items.map((item) => (
        <div key={item.label} className='space-y-1'>
          <p className='text-xs uppercase tracking-[0.14em] text-[#6a7282]'>{item.label}</p>
          <p className='text-sm text-[#d1d5dc]'>{item.value || '-'}</p>
        </div>
      ))}
    </div>
  );
}

function ReviewSection({
  title,
  onEdit,
  children,
}: {
  title: string;
  onEdit: () => void;
  children: React.ReactNode;
}) {
  return (
    <section className='rounded-[12px] border border-[#364153] bg-[#101828] p-5'>
      <div className='mb-5 flex items-center justify-between gap-3'>
        <h3 className='text-lg font-medium text-white'>{title}</h3>
        <button type='button' onClick={onEdit} className={tertiaryButtonClass}>
          <Pencil size={14} />
          Editar
        </button>
      </div>
      {children}
    </section>
  );
}

export const StepRevisao: React.FC<Props> = ({ data, onEdit }) => {
  const passengerSummary = getPassengerSummary(data);

  return (
    <div className='space-y-6'>
      <div className='space-y-2'>
        <h2 className='text-[24px] font-semibold leading-8 text-white'>Revisão Final</h2>
        <p className='text-base text-[#99a1af]'>Confira todos os dados antes de finalizar a emissão</p>
      </div>

      <ReviewSection title='Cliente & Programa' onEdit={() => onEdit(1)}>
        <ReviewGrid
          items={[
            { label: 'Tipo de Emissão', value: getEmissionTypeLabel(data.tipoEmissao) },
            { label: 'Cliente', value: getClientLabel(data.clienteId) },
            { label: 'Programa', value: getProgramLabel(data.programaId) },
          ]}
        />
      </ReviewSection>

      <ReviewSection title='Voos' onEdit={() => onEdit(2)}>
        <div className='space-y-5'>
          <div className='space-y-3'>
            <p className='text-sm font-medium text-white'>Voo de Ida</p>
            <ReviewGrid
              items={[
                { label: 'Origem', value: data.vooIda.origem || '-' },
                { label: 'Destino', value: data.vooIda.destino || '-' },
                { label: 'Companhia', value: data.vooIda.companhia || '-' },
                { label: 'Data/Hora', value: formatDateTime(data.vooIda.dataHora) },
              ]}
            />
          </div>

          {data.possuiVolta && (
            <div className='space-y-3 border-t border-[#364153] pt-5'>
              <p className='text-sm font-medium text-white'>Voo de Volta</p>
              <ReviewGrid
                items={[
                  { label: 'Origem', value: data.vooVolta.origem || '-' },
                  { label: 'Destino', value: data.vooVolta.destino || '-' },
                  { label: 'Companhia', value: data.vooVolta.companhia || '-' },
                  { label: 'Data/Hora', value: formatDateTime(data.vooVolta.dataHora) },
                ]}
              />
            </div>
          )}
        </div>
      </ReviewSection>

      <ReviewSection title='Passageiros' onEdit={() => onEdit(4)}>
        <p className='text-sm text-[#d1d5dc]'>{passengerSummary.label}</p>
      </ReviewSection>

      <ReviewSection title='Valores' onEdit={() => onEdit(5)}>
        <div className='grid gap-4 md:grid-cols-2 xl:grid-cols-3'>
          <div className={statCardClass}>
            <p className='text-xs uppercase tracking-[0.14em] text-[#6a7282]'>Milhas</p>
            <p className='mt-2 text-xl font-semibold text-white'>{data.valores.quantidadeMilhas.toLocaleString('pt-BR')}</p>
          </div>
          <div className={statCardClass}>
            <p className='text-xs uppercase tracking-[0.14em] text-[#6a7282]'>Custo Milhas</p>
            <p className='mt-2 text-xl font-semibold text-white'>{formatCurrency(data.valores.custoMilhas)}</p>
          </div>
          <div className={statCardClass}>
            <p className='text-xs uppercase tracking-[0.14em] text-[#6a7282]'>Taxas</p>
            <p className='mt-2 text-xl font-semibold text-white'>{formatCurrency(data.valores.taxas)}</p>
          </div>
          <div className={statCardClass}>
            <p className='text-xs uppercase tracking-[0.14em] text-[#6a7282]'>Valor Total</p>
            <p className='mt-2 text-xl font-semibold text-white'>{formatCurrency(data.valores.valorTotalFinal)}</p>
          </div>
          <div className={statCardClass}>
            <p className='text-xs uppercase tracking-[0.14em] text-[#6a7282]'>Lucro</p>
            <p className={`mt-2 text-xl font-semibold ${data.valores.lucro >= 0 ? 'text-[#00c950]' : 'text-[#f87171]'}`}>
              {formatCurrency(data.valores.lucro)}
            </p>
          </div>
          <div className={statCardClass}>
            <p className='text-xs uppercase tracking-[0.14em] text-[#6a7282]'>Economia Cliente</p>
            <p className='mt-2 text-xl font-semibold text-[#60a5fa]'>{formatCurrency(data.valores.economiaObtida)}</p>
          </div>
        </div>
      </ReviewSection>

      <div className='rounded-[12px] border border-[#14532d] bg-[#163322] p-5'>
        <div className='flex gap-3'>
          <CheckCircle2 className='mt-0.5 text-[#00c950]' size={20} />
          <div>
            <p className='text-base font-medium text-white'>Pronto para finalizar</p>
            <p className='mt-2 text-sm text-[#a7f3d0]'>
              Revise as informações acima. Ao finalizar, a emissão será registrada e você será redirecionado para a listagem.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
