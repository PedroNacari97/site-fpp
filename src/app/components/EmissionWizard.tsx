import React, { useEffect, useMemo, useState } from 'react';
import { EmissionSidebar } from './wizard-steps/EmissionSidebar';
import { StepCliente } from './wizard-steps/StepCliente';
import { StepPassageiros } from './wizard-steps/StepPassageiros';
import { StepRevisao } from './wizard-steps/StepRevisao';
import { StepValores } from './wizard-steps/StepValores';
import { StepVooIda } from './wizard-steps/StepVooIda';
import { StepVooVolta } from './wizard-steps/StepVooVolta';
import { EmissionData, StepId } from './wizard-steps/types';
import { useEmissionValidation } from '../hooks/useEmissionValidation';
import { validateAll } from '../utils/emissionValidation';
import { ChevronLeft, ChevronRight } from 'lucide-react';
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

const baseBtn = 'h-10 px-4 rounded-lg transition-all duration-200 active:scale-95';

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
    return <StepRevisao data={emissionData} loading={isSaving} onEdit={(step) => setCurrentStep(step as StepId)} onFinish={handleFinish} />;
  }, [currentStep, emissionData, errors, isSaving]);

  return (
    <div className='p-6 space-y-6 bg-gray-50 min-h-screen'>
      <header className='space-y-2'>
        <h1 className='text-2xl font-semibold text-gray-900'>Nova Emissão</h1>
        <p className='text-sm text-gray-500'>Preencha os dados para criar uma nova emissão.</p>
      </header>

      <div className='bg-white border border-gray-200 rounded-xl shadow-sm p-6'>
        <WizardStepper currentStep={currentStep} onStepClick={handleStepClick} />
      </div>

      <div className='grid grid-cols-12 gap-6'>
        <div className='col-span-12 lg:col-span-8 bg-white border border-gray-200 rounded-xl shadow-sm p-6 space-y-6'>
          {currentStepComponent}
          <div className='flex items-center justify-between'>
            <button
              type='button'
              onClick={handlePrevious}
              disabled={currentStep === 1}
              className={`${baseBtn} border border-gray-300 text-gray-900 disabled:bg-gray-300 disabled:cursor-not-allowed hover:shadow-md`}
            >
              <ChevronLeft size={16} /> Voltar
            </button>
            {currentStep < 6 && (
              <button
                type='button'
                onClick={handleNext}
                className={`${baseBtn} bg-blue-600 text-white hover:bg-blue-700 hover:shadow-md`}
              >
                Próximo <ChevronRight size={16} />
              </button>
            )}
          </div>
        </div>

        <div className='col-span-12 lg:col-span-4'>
          <EmissionSidebar data={emissionData} lastSavedAt={lastSavedAt} />
        </div>
      </div>
    </div>
  );
};

export default EmissionWizard;
