#include "device.h"
#include "app_config.h"
#include "fpga_link.h"
#include "protocol.h"
#include "crc32.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static uint32_t now, fpga_generation;
static bool link_ok=true, stop_ok=true, button=false;
static unsigned writes, checks; static unsigned table_bytes; static bool table_write_ok=true;
static uint8_t reply[1100]; static size_t reply_len;
#define CHECK(x) do { assert(x); ++checks; } while(0)
uint32_t board_millis(void) { return now; }
bool board_stop_pressed(void) { return button; }
bool board_power_good(void) { return true; }
bool board_a_present(void) { return true; }
bool board_b_present(void) { return true; }
bool fpga_link_probe(void) { return link_ok; }
bool fpga_link_stop(void) { return link_ok && stop_ok; }
bool fpga_link_start(void) { return link_ok; }
bool fpga_link_write_channel(uint8_t channel,const channel_config_t *c) {
 CHECK(channel==0 && c!=NULL); ++writes;return link_ok;
}
bool fpga_link_commit(uint32_t generation) { fpga_generation=generation;return link_ok; }
bool fpga_link_status(fpga_status_t *s) { memset(s,0,sizeof(*s));s->active_generation=fpga_generation;return link_ok; }
bool fpga_link_select_preset(uint8_t x) { (void)x;return false; }
bool fpga_link_data_begin(uint32_t x) { table_bytes=0;return x==256; }
bool fpga_link_data_write(uint32_t x,const uint8_t *p,size_t n) { (void)p; if(!table_write_ok || x!=table_bytes)return false;table_bytes+=(unsigned)n;return true; }
bool fpga_link_data_end(uint32_t x) { (void)x;return table_bytes==256; }
const char *fpga_link_version(void) { return "FPGA-4.0.0"; }
void ui_force_refresh(void) { }
uint32_t transport_rx_overflows(void) { return 0; }
void transport_write(const uint8_t *p,size_t n) { assert(n<=sizeof(reply));memcpy(reply,p,n);reply_len=n; }
bool storage_save_profile(uint8_t id,const channel_config_t *p) { (void)id;(void)p;return false; }
bool storage_load_profile(uint8_t id,channel_config_t *p) { (void)id;(void)p;return false; }
static void put16(uint8_t *p,uint16_t n) { p[0]=n;p[1]=n>>8; }
static void put32(uint8_t *p,uint32_t n) { for(unsigned j=0;j<4;j++)p[j]=(uint8_t)(n>>(8*j)); }
static void raw_request(uint16_t cmd,const uint8_t *json,size_t n,bool expect_error) {
 static uint16_t seq;uint8_t f[1100];++seq;
 f[0]=0xa5;f[1]=0x5a;f[2]=1;f[3]=1;put16(f+4,cmd);put16(f+6,seq);put32(f+8,(uint32_t)n);
 memcpy(f+12,json,n);put32(f+12+n,crc32_compute(f+2,n+10));reply_len=0;
 /* Deliberately split a frame across two feed calls. */
 protocol_feed(f,7);protocol_poll();CHECK(reply_len==0);
 protocol_feed(f+7,n+9);protocol_poll();CHECK(reply_len>=16);
 CHECK(((reply[3]&4)!=0)==expect_error);
 uint32_t crc;memcpy(&crc,reply+reply_len-4,4);CHECK(crc==crc32_compute(reply+2,reply_len-6));
 reply[reply_len-4]=0;
}
static void request(uint16_t cmd,const char *json,bool error) { raw_request(cmd,(const uint8_t*)json,strlen(json),error); }

int main(void) {
 device_init();protocol_init();CHECK(g_device.state==DEVICE_IDLE);
 request(1,"{}",false);CHECK(strstr((char*)reply+12,"F405-N4.0.0")!=NULL);
 const char *fast="{\"channel\":1,\"random_events\":0,\"noise_peak_codes\":0,\"spectrum_enabled\":0,\"seed\":1,\"dac_baseline_code\":96,\"dac_amplitude_code\":84,\"decay_us\":1,\"mean_interval_us\":10,\"noise_mode\":\"uniform\",\"noise_rms_percent\":0,\"allow_pileup\":0}";
 request(0x10,fast,false);request(0x11,"{}",false);request(0x30,"{}",false);
 CHECK(g_device.active[0].interval_us==10);request(0x31,"{}",false);
 request(0x10,"{\"channel\":1,\"random_events\":0,\"noise_peak_codes\":0,\"spectrum_enabled\":0,\"seed\":17,\"dac_baseline_code\":128,\"dac_amplitude_code\":0,\"decay_us\":145,\"mean_interval_us\":1000,\"noise_mode\": \"gaussian\",\"noise_rms_percent\":20,\"allow_pileup\":0}",false);
 CHECK(g_device.shadow[0].noise_mode==1 && g_device.shadow[0].noise_percent==20);
 request(0x11,"{}",false);request(0x30,"{}",false);request(2,"{}",false);
 CHECK(strstr((char*)reply+12,"\"noise_rms_percent\":20")!=NULL);
 CHECK(strstr((char*)reply+12,"\"noise_peak_codes\":0")!=NULL);
 request(0x20,"{\"bytes\":256}",true);
 now=2100;device_poll();CHECK(g_device.error==DEV_ERR_TRANSFER);
 request(0x70,"{}",false);
 request(0x10,"{\"channel\":1,\"random_events\":0,\"noise_peak_codes\":0,\"spectrum_enabled\":0,\"mean_interval_us\":10,\"noise_mode\":\"gaussian\",\"noise_rms_percent\":21,\"allow_pileup\":0}",true);
 request(0x10,"{\"channel\":1,\"random_events\":0,\"noise_peak_codes\":0,\"spectrum_enabled\":0,\"noise_mode\":\"gaussian\",\"noise_rms_percent\":1.5,\"allow_pileup\":0}",true);
 request(0x10,"{\"channel\":1,\"random_events\":0,\"noise_peak_codes\":0,\"spectrum_enabled\":0,\"noise_mode\":\"gaussian\",\"noise_rms_percent\":-1,\"allow_pileup\":0}",true);
 request(0x10,"{\"channel\":1,\"random_events\":0,\"noise_peak_codes\":0,\"spectrum_enabled\":0,\"noise_mode\":\"unknown\",\"noise_rms_percent\":0,\"allow_pileup\":0}",true);
 channel_config_t c=g_device.shadow[0];c.interval_us=9;CHECK(!device_set_channel(0,&c));
 c=g_device.shadow[0];c.interval_us=10;c.decay_us=100;c.arrival_mode=0;c.pileup_mode=0;CHECK(!device_set_channel(0,&c));
 c.pileup_mode=1;CHECK(device_set_channel(0,&c));
 c.arrival_mode=1;CHECK(!device_set_channel(0,&c)); // Random minimum remains128.
 c.interval_us=128;CHECK(device_set_channel(0,&c));
 c.decay_us=146;CHECK(!device_set_channel(0,&c));c.decay_us=NAN;CHECK(!device_set_channel(0,&c));
 c=g_device.shadow[0];c.interval_us=1000;c.decay_us=145;CHECK(device_set_channel(0,&c));
 request(0x11,"{}",false);request(0x30,"{}",false);
 button=true;device_poll();CHECK(g_device.state==DEVICE_IDLE);
 button=false;now+=5000;device_poll();CHECK(g_device.state!=DEVICE_RUNNING);
 request(0x30,"{}",true);
 printf("PASS: STM32 competition N4 %u checks (mock FPGA and GPIO)\n",checks);return 0;
}
