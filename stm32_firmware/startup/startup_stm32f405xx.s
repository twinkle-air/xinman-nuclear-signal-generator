.syntax unified
.cpu cortex-m4
.fpu fpv4-sp-d16
.thumb

.global g_pfnVectors
.global Default_Handler

.word _sidata
.word _sdata
.word _edata
.word _sbss
.word _ebss

.section .text.Reset_Handler
.weak Reset_Handler
.type Reset_Handler, %function
.thumb_func
Reset_Handler:
  ldr sp, =_estack
  ldr r0, =_sdata
  ldr r1, =_edata
  ldr r2, =_sidata
1: cmp r0, r1
  ittt lt
  ldrlt r3, [r2], #4
  strlt r3, [r0], #4
  blt 1b
  ldr r0, =_sbss
  ldr r1, =_ebss
  movs r2, #0
2: cmp r0, r1
  itt lt
  strlt r2, [r0], #4
  blt 2b
  bl SystemInit
  bl __libc_init_array
  bl main
3: b 3b
.size Reset_Handler, .-Reset_Handler

.section .text.Default_Handler,"ax",%progbits
.type Default_Handler, %function
.thumb_func
Default_Handler:
  b Default_Handler
.size Default_Handler, .-Default_Handler

.macro weak_handler name
  .weak \name
  .type \name, %function
  .thumb_func
\name:
  b Default_Handler
  .size \name, .-\name
.endm

weak_handler NMI_Handler
weak_handler HardFault_Handler
weak_handler MemManage_Handler
weak_handler BusFault_Handler
weak_handler UsageFault_Handler
weak_handler SVC_Handler
weak_handler DebugMon_Handler
weak_handler PendSV_Handler
weak_handler SysTick_Handler
weak_handler WWDG_IRQHandler
weak_handler PVD_IRQHandler
weak_handler TAMP_STAMP_IRQHandler
weak_handler RTC_WKUP_IRQHandler
weak_handler FLASH_IRQHandler
weak_handler RCC_IRQHandler
weak_handler EXTI0_IRQHandler
weak_handler EXTI1_IRQHandler
weak_handler EXTI2_IRQHandler
weak_handler EXTI3_IRQHandler
weak_handler EXTI4_IRQHandler
weak_handler DMA1_Stream0_IRQHandler
weak_handler DMA1_Stream1_IRQHandler
weak_handler DMA1_Stream2_IRQHandler
weak_handler DMA1_Stream3_IRQHandler
weak_handler DMA1_Stream4_IRQHandler
weak_handler DMA1_Stream5_IRQHandler
weak_handler DMA1_Stream6_IRQHandler
weak_handler ADC_IRQHandler
weak_handler CAN1_TX_IRQHandler
weak_handler CAN1_RX0_IRQHandler
weak_handler CAN1_RX1_IRQHandler
weak_handler CAN1_SCE_IRQHandler
weak_handler EXTI9_5_IRQHandler
weak_handler TIM1_BRK_TIM9_IRQHandler
weak_handler TIM1_UP_TIM10_IRQHandler
weak_handler TIM1_TRG_COM_TIM11_IRQHandler
weak_handler TIM1_CC_IRQHandler
weak_handler TIM2_IRQHandler
weak_handler TIM3_IRQHandler
weak_handler TIM4_IRQHandler
weak_handler I2C1_EV_IRQHandler
weak_handler I2C1_ER_IRQHandler
weak_handler I2C2_EV_IRQHandler
weak_handler I2C2_ER_IRQHandler
weak_handler SPI1_IRQHandler
weak_handler SPI2_IRQHandler
weak_handler USART1_IRQHandler
weak_handler USART2_IRQHandler
weak_handler USART3_IRQHandler
weak_handler EXTI15_10_IRQHandler
weak_handler RTC_Alarm_IRQHandler
weak_handler OTG_FS_WKUP_IRQHandler
weak_handler TIM8_BRK_TIM12_IRQHandler
weak_handler TIM8_UP_TIM13_IRQHandler
weak_handler TIM8_TRG_COM_TIM14_IRQHandler
weak_handler TIM8_CC_IRQHandler
weak_handler DMA1_Stream7_IRQHandler
weak_handler FSMC_IRQHandler
weak_handler SDIO_IRQHandler
weak_handler TIM5_IRQHandler
weak_handler SPI3_IRQHandler
weak_handler UART4_IRQHandler
weak_handler UART5_IRQHandler
weak_handler TIM6_DAC_IRQHandler
weak_handler TIM7_IRQHandler
weak_handler DMA2_Stream0_IRQHandler
weak_handler DMA2_Stream1_IRQHandler
weak_handler DMA2_Stream2_IRQHandler
weak_handler DMA2_Stream3_IRQHandler
weak_handler DMA2_Stream4_IRQHandler
weak_handler ETH_IRQHandler
weak_handler ETH_WKUP_IRQHandler
weak_handler CAN2_TX_IRQHandler
weak_handler CAN2_RX0_IRQHandler
weak_handler CAN2_RX1_IRQHandler
weak_handler CAN2_SCE_IRQHandler
weak_handler OTG_FS_IRQHandler
weak_handler DMA2_Stream5_IRQHandler
weak_handler DMA2_Stream6_IRQHandler
weak_handler DMA2_Stream7_IRQHandler
weak_handler USART6_IRQHandler
weak_handler I2C3_EV_IRQHandler
weak_handler I2C3_ER_IRQHandler
weak_handler OTG_HS_EP1_OUT_IRQHandler
weak_handler OTG_HS_EP1_IN_IRQHandler
weak_handler OTG_HS_WKUP_IRQHandler
weak_handler OTG_HS_IRQHandler
weak_handler DCMI_IRQHandler
weak_handler CRYP_IRQHandler
weak_handler HASH_RNG_IRQHandler
weak_handler FPU_IRQHandler

.section .isr_vector,"a",%progbits
.type g_pfnVectors, %object
g_pfnVectors:
  .word _estack
  .word Reset_Handler
  .word NMI_Handler
  .word HardFault_Handler
  .word MemManage_Handler
  .word BusFault_Handler
  .word UsageFault_Handler
  .word 0,0,0,0
  .word SVC_Handler
  .word DebugMon_Handler
  .word 0
  .word PendSV_Handler
  .word SysTick_Handler
  .word WWDG_IRQHandler,PVD_IRQHandler,TAMP_STAMP_IRQHandler,RTC_WKUP_IRQHandler
  .word FLASH_IRQHandler,RCC_IRQHandler,EXTI0_IRQHandler,EXTI1_IRQHandler
  .word EXTI2_IRQHandler,EXTI3_IRQHandler,EXTI4_IRQHandler
  .word DMA1_Stream0_IRQHandler,DMA1_Stream1_IRQHandler,DMA1_Stream2_IRQHandler
  .word DMA1_Stream3_IRQHandler,DMA1_Stream4_IRQHandler,DMA1_Stream5_IRQHandler
  .word DMA1_Stream6_IRQHandler,ADC_IRQHandler,CAN1_TX_IRQHandler,CAN1_RX0_IRQHandler
  .word CAN1_RX1_IRQHandler,CAN1_SCE_IRQHandler,EXTI9_5_IRQHandler
  .word TIM1_BRK_TIM9_IRQHandler,TIM1_UP_TIM10_IRQHandler,TIM1_TRG_COM_TIM11_IRQHandler
  .word TIM1_CC_IRQHandler,TIM2_IRQHandler,TIM3_IRQHandler,TIM4_IRQHandler
  .word I2C1_EV_IRQHandler,I2C1_ER_IRQHandler,I2C2_EV_IRQHandler,I2C2_ER_IRQHandler
  .word SPI1_IRQHandler,SPI2_IRQHandler,USART1_IRQHandler,USART2_IRQHandler,USART3_IRQHandler
  .word EXTI15_10_IRQHandler,RTC_Alarm_IRQHandler,OTG_FS_WKUP_IRQHandler
  .word TIM8_BRK_TIM12_IRQHandler,TIM8_UP_TIM13_IRQHandler,TIM8_TRG_COM_TIM14_IRQHandler
  .word TIM8_CC_IRQHandler,DMA1_Stream7_IRQHandler,FSMC_IRQHandler,SDIO_IRQHandler
  .word TIM5_IRQHandler,SPI3_IRQHandler,UART4_IRQHandler,UART5_IRQHandler
  .word TIM6_DAC_IRQHandler,TIM7_IRQHandler,DMA2_Stream0_IRQHandler,DMA2_Stream1_IRQHandler
  .word DMA2_Stream2_IRQHandler,DMA2_Stream3_IRQHandler,DMA2_Stream4_IRQHandler
  .word ETH_IRQHandler,ETH_WKUP_IRQHandler,CAN2_TX_IRQHandler,CAN2_RX0_IRQHandler
  .word CAN2_RX1_IRQHandler,CAN2_SCE_IRQHandler,OTG_FS_IRQHandler
  .word DMA2_Stream5_IRQHandler,DMA2_Stream6_IRQHandler,DMA2_Stream7_IRQHandler
  .word USART6_IRQHandler,I2C3_EV_IRQHandler,I2C3_ER_IRQHandler
  .word OTG_HS_EP1_OUT_IRQHandler,OTG_HS_EP1_IN_IRQHandler,OTG_HS_WKUP_IRQHandler
  .word OTG_HS_IRQHandler,DCMI_IRQHandler,CRYP_IRQHandler,HASH_RNG_IRQHandler,FPU_IRQHandler
.size g_pfnVectors, .-g_pfnVectors
