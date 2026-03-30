import React, { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { useEmissionValidation } from '../hooks/useEmissionValidation';
import { validateAll } from '../utils/emissionValidation';
import { EmissionSidebar } from './wizard-steps/EmissionSidebar';
import { StepCliente } from './wizard-steps/StepCliente';
import { StepPassageiros } from './wizard-steps/StepPassageiros';
import { StepRevisao } from './wizard-steps/StepRevisao';
import { StepValores } from './wizard-steps/StepValores';
import { StepVooIda } from './wizard-steps/StepVooIda';
import { StepVooVolta } from './wizard-steps/StepVooVolta';
import {
  cn,
  headerDescriptionClass,
  headerTitleClass,
  pageShellClass,
  primaryButtonClass,
  secondaryButtonClass,
  surfaceCardClass,
} from './wizard-steps/theme';
import { EmissionData, StepId } from './wizard-steps/types';
import { WizardStepper } from './wizard-steps/WizardStepper';

const STORAGE_KEY = 'emission_wizard_draft';

const initialData: EmissionData = {
  tipoEmissao: '',
  clienteId: '',
  programaId: '',
  vooIda: { origem: '', destino: '', companhia: '', dataHora: '', possuiEscala: false, escalas: [] },
  possuiVolta: false,
  vooVolta: { origem: '', destino: '', companhia: '', dataHora: '', possuiEscala: false, escalas: [] },
  passageiros: [],
  valores: {
    quantidadeMilhas: 0,
    custoMilhas: 0,
    taxas: 0,
    valorMilheiros: 0,
    valorFinalCliente: 0,
    valorTotalFinal: 0,
    lucro: 0,
    margemPercentual: 0,
    valorReferencia: 0,
    economiaObtida: 0,
    economiaPercentual: 0,
  },
  localizador: '',
  observacoes: '',
};

const mockCreateEmission = () =>
  new Promise<{ id: string }>((resolve) => setTimeout(() => resolve({ id: `EM-${Date.now()}` }), 1000));

export const EmissionWizard: React.FC = () => {
  const [currentStep, setCurrentStep] = useState<StepId>(1);
  const [emissionData, setEmissionData] = useState<EmissionData>(initialData);
  const [lastSavedAt, setLastSavedAt] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const { errors } = useEmissionValidation(currentStep, emissionData);

  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as { step: StepId; data: EmissionData };
      setEmissionData(parsed.data);
      setCurrentStep(parsed.step);
    } catch {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ step: currentStep, data: emissionData }));
    setLastSavedAt(new Date().toLocaleTimeString('pt-BR'));
  }, [currentStep, emissionData]);

  useEffect(() => {
    const { quantidadeMilhas, custoMilhas, taxas, valorTotalFinal, valorReferencia } = emissionData.valores;
    const valorMilheiros = (quantidadeMilhas / 1000) * custoMilhas;
    const valorFinalCliente = valorMilheiros + taxas;
    const lucro = valorTotalFinal - valorMilheiros - taxas;
    const margemPercentual = valorTotalFinal > 0 ? (lucro / valorTotalFinal) * 100 : 0;
    const economiaObtida = valorReferencia > 0 ? valorReferencia - valorTotalFinal : 0;
    const economiaPercentual = valorReferencia > 0 ? (economiaObtida / valorReferencia) * 100 : 0;

    setEmissionData((prev) => ({
      ...prev,
      valores: {
        ...prev.valores,
        valorMilheiros,
        valorFinalCliente,
        lucro,
        margemPercentual,
        economiaObtida,
        economiaPercentual,
      },
    }));
  }, [
    emissionData.valores.quantidadeMilhas,
    emissionData.valores.custoMilhas,
    emissionData.valores.taxas,
    emissionData.valores.valorTotalFinal,
    emissionData.valores.valorReferencia,
  ]);

  const updateEmissionData = (patch: Partial<EmissionData>) => {
    setEmissionData((prev) => ({ ...prev, ...patch }));
  };

  const handleNext = () => {
    if (Object.keys(errors).length) return;
    setCurrentStep((prev) => Math.min(6, (prev + 1) as StepId));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handlePrevious = () => {
    setCurrentStep((prev) => Math.max(1, (prev - 1) as StepId));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleStepClick = (stepId: StepId) => {
    if (stepId <= currentStep) {
      setCurrentStep(stepId);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleFinish = async () => {
    const allErrors = validateAll(emissionData);
    if (Object.keys(allErrors).length) {
      alert('Existem campos pendentes. Revise as etapas antes de finalizar.');
      return;
    }

    setIsSaving(true);
    await mockCreateEmission();
    localStorage.removeItem(STORAGE_KEY);
    setIsSaving(false);
    window.location.assign('/admin/emissoes/');
  };

  const currentStepComponent = useMemo(() => {
    const props = { data: emissionData, errors, onUpdate: updateEmissionData };
    if (currentStep === 1) return <StepCliente {...props} />;
    if (currentStep === 2) return <StepVooIda {...props} />;
    if (currentStep === 3) return <StepVooVolta {...props} />;
    if (currentStep === 4) return <StepPassageiros {...props} />;
    if (currentStep === 5) return <StepValores {...props} />;
    return <StepRevisao data={emissionData} onEdit={(step) => setCurrentStep(step as StepId)} />;
  }, [currentStep, emissionData, errors]);

  return (
    <div
      className={cn(
        pageShellClass,
        'bg-[radial-gradient(circle_at_top,_rgba(21,93,252,0.18),_transparent_26%),#101828]',
      )}
    >
      <div className='mx-auto flex max-w-[1120px] flex-col gap-8'>
        <header className='space-y-2'>
          <h1 className={headerTitleClass}>Nova Emissão</h1>
          <p className={headerDescriptionClass}>Preencha os dados para criar uma nova emissão de passagem</p>
        </header>

        <section className={cn(surfaceCardClass, 'p-6 sm:p-8')}>
          <WizardStepper currentStep={currentStep} onStepClick={handleStepClick} />
        </section>

        <div className='grid grid-cols-1 gap-8 xl:grid-cols-[minmax(0,1fr)_341px] xl:items-start'>
          <div className='space-y-6'>
            <section className={cn(surfaceCardClass, 'p-6 sm:p-8')}>
              {currentStepComponent}
            </section>

            <div className='flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between'>
              <button
                type='button'
                onClick={handlePrevious}
                disabled={currentStep === 1 || isSaving}
                className={cn(secondaryButtonClass, 'justify-center px-6 sm:min-w-[124px]')}
              >
                <ChevronLeft size={18} />
                Voltar
              </button>

              {currentStep < 6 ? (
                <button
                  type='button'
                  onClick={handleNext}
                  disabled={isSaving}
                  className={cn(primaryButtonClass, 'justify-center px-6 sm:min-w-[146px]')}
                >
                  Próximo
                  <ChevronRight size={18} />
                </button>
              ) : (
                <button
                  type='button'
                  onClick={handleFinish}
                  disabled={isSaving}
                  className={cn(primaryButtonClass, 'justify-center px-6 sm:min-w-[186px]')}
                >
                  {isSaving ? (
                    <>
                      <Loader2 size={18} className='animate-spin' />
                      Finalizando...
                    </>
                  ) : (
                    'Finalizar Emissão'
                  )}
                </button>
              )}
            </div>
          </div>

          <EmissionSidebar data={emissionData} lastSavedAt={lastSavedAt} />
        </div>
      </div>
    </div>
  );
};

export default EmissionWizard;
