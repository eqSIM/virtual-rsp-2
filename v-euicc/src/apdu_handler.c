#include "apdu_handler.h"
#include "cert_loader.h"
#include "crypto.h"
#include <euicc/hexutil.h>
#include <openssl/evp.h>
#include <openssl/ec.h>
#include <openssl/bn.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "../logging.h"

// Forward declaration
static void build_tlv(uint8_t **buffer, uint32_t *buffer_len, uint16_t tag, const uint8_t *value, uint32_t value_len);

// Helper: Build complete euiccInfo2 structure (reusable)
static int build_euiccinfo2(uint8_t **output_buf, uint32_t *output_len) {
    // Build EUICCInfo2 with proper ASN.1 encoding
    // Each field must have its correct tag and encoding

    uint8_t *buffer = NULL;
    uint32_t buffer_len = 0;
    uint8_t *ptr;

    // Estimate buffer size - EUICCInfo2 is complex, allocate generously
    buffer = malloc(1024);
    if (!buffer) {
        return -1;
    }
    ptr = buffer;

    // profileVersion [1] VersionType ::= OCTET STRING(SIZE(3))
    // VersionType: major/minor/revision as binary values, e.g. '02 01 00' for v2.1.0
    uint8_t profile_version[] = {0x81, 0x03, 0x02, 0x01, 0x00};  // [1] + 3-byte OCTET STRING + value
    memcpy(ptr, profile_version, sizeof(profile_version));
    ptr += sizeof(profile_version);
    buffer_len += sizeof(profile_version);

    // svn [2] VersionType - SGP.22 version supported (SVN)
    // Use 2.2.0 as in the specification
    uint8_t svn[] = {0x82, 0x03, 0x02, 0x02, 0x00};  // [2] + 3-byte OCTET STRING + value
    memcpy(ptr, svn, sizeof(svn));
    ptr += sizeof(svn);
    buffer_len += sizeof(svn);

    // euiccFirmwareVer [3] VersionType - eUICC Firmware version
    uint8_t firmware_ver[] = {0x83, 0x03, 0x01, 0x00, 0x00};  // [3] + 3-byte OCTET STRING + value
    memcpy(ptr, firmware_ver, sizeof(firmware_ver));
    ptr += sizeof(firmware_ver);
    buffer_len += sizeof(firmware_ver);

    // extCardResource [4] OCTET STRING - Extended Card Resource Information
    // CRITICAL FIX: Length was 0x0C (12 bytes) but data is 13 bytes - changed to 0x0D
    uint8_t ext_card_res[] = {0x84, 0x0D, 0x81, 0x01, 0x00, 0x82, 0x04, 0x00, 0x04, 0x9C, 0x68, 0x83, 0x02, 0x22, 0x23};
    memcpy(ptr, ext_card_res, sizeof(ext_card_res));
    ptr += sizeof(ext_card_res);
    buffer_len += sizeof(ext_card_res);

    // uiccCapability [5] UICCCapability ::= BIT STRING
    // Match pySim encoding: single byte 0x00 (no capabilities set)
    uint8_t uicc_cap[] = {0x85, 0x01, 0x00};  // [5] + length(1) + data(0x00)
    memcpy(ptr, uicc_cap, sizeof(uicc_cap));
    ptr += sizeof(uicc_cap);
    buffer_len += sizeof(uicc_cap);

    // javacardVersion [6] VersionType OPTIONAL - include for compatibility
    uint8_t javacard_ver[] = {0x86, 0x03, 0x11, 0x02, 0x00};  // [6] + 3-byte OCTET STRING + value
    memcpy(ptr, javacard_ver, sizeof(javacard_ver));
    ptr += sizeof(javacard_ver);
    buffer_len += sizeof(javacard_ver);

    // globalplatformVersion [7] VersionType OPTIONAL - include for compatibility
    uint8_t gp_ver[] = {0x87, 0x03, 0x02, 0x03, 0x00};  // [7] + 3-byte OCTET STRING + value
    memcpy(ptr, gp_ver, sizeof(gp_ver));
    ptr += sizeof(gp_ver);
    buffer_len += sizeof(gp_ver);

    // rspCapability [8] RspCapability ::= BIT STRING
    // CRITICAL FIX: Must match pySim exactly - data byte is 0x9c not 0x28
    uint8_t rsp_cap[] = {0x88, 0x02, 0x02, 0x9c};  // [8] + length(2) + unused_bits(2) + data(9c)
    memcpy(ptr, rsp_cap, sizeof(rsp_cap));
    ptr += sizeof(rsp_cap);
    buffer_len += sizeof(rsp_cap);

    // euiccCiPKIdListForVerification [9] SEQUENCE OF SubjectKeyIdentifier
    // CRITICAL FIX: SEQUENCE OF must use constructed tag (0xA9) not primitive (0x89)
    uint8_t ci_pk_verify[] = {0xA9, 0x00};  // [9] CONSTRUCTED + empty sequence
    memcpy(ptr, ci_pk_verify, sizeof(ci_pk_verify));
    ptr += sizeof(ci_pk_verify);
    buffer_len += sizeof(ci_pk_verify);

    // euiccCiPKIdListForSigning [10] SEQUENCE OF SubjectKeyIdentifier
    // CRITICAL FIX: SEQUENCE OF must use constructed tag (0xAA) not primitive (0x8A)
    uint8_t ci_pk_sign[] = {0xAA, 0x00};  // [10] CONSTRUCTED + empty sequence
    memcpy(ptr, ci_pk_sign, sizeof(ci_pk_sign));
    ptr += sizeof(ci_pk_sign);
    buffer_len += sizeof(ci_pk_sign);

    // ppVersion VersionType - needs OCTET STRING tag (matches pySim encoding)
    uint8_t pp_ver[] = {0x04, 0x03, 0x01, 0x00, 0x00};  // OCTET STRING + length + data
    memcpy(ptr, pp_ver, sizeof(pp_ver));
    ptr += sizeof(pp_ver);
    buffer_len += sizeof(pp_ver);

    // sasAcreditationNumber UTF8String
    uint8_t sas_acred[] = {0x4F, 0x53, 0x4D, 0x4F, 0x43, 0x4F, 0x4D, 0x2D, 0x54, 0x45, 0x53, 0x54, 0x2D, 0x31}; // "OSMOCOM-TEST-1"
    uint8_t sas_len = sizeof(sas_acred);
    *ptr++ = 0x0C; // UTF8String tag
    *ptr++ = sas_len;
    memcpy(ptr, sas_acred, sas_len);
    ptr += sas_len;
    buffer_len += 2 + sas_len;

    // Debug: Print euiccInfo2 raw data (without BF22 wrapper)
    fprintf(stderr, "DEBUG: euiccInfo2 raw data (%u bytes):\n", buffer_len);
    for (uint32_t i = 0; i < buffer_len; i++) {
        fprintf(stderr, "%02x", buffer[i]);
    }
    fprintf(stderr, "\n");

    *output_buf = buffer;
    *output_len = buffer_len;
    return 0;
}

// Helper: Build DER-TLV response
static void build_tlv(uint8_t **buffer, uint32_t *buffer_len, uint16_t tag, const uint8_t *value, uint32_t value_len) {
    uint32_t total_len = 0;
    uint8_t *ptr;

    // Calculate total length
    if (tag >> 8) {
        total_len += 2; // 2-byte tag
    } else {
        total_len += 1; // 1-byte tag
    }

    if (value_len < 0x80) {
        total_len += 1; // 1-byte length
    } else {
        uint8_t lengthlen = 0;
        uint32_t tmp_len = value_len;
        while (tmp_len) {
            tmp_len >>= 8;
            lengthlen++;
        }
        total_len += 1 + lengthlen; // length of length + length bytes
    }

    total_len += value_len;

    *buffer = malloc(total_len);
    if (!*buffer) {
        *buffer_len = 0;
        return;
    }

    ptr = *buffer;

    // Write tag
    if (tag >> 8) {
        *ptr++ = tag >> 8;
    }
    *ptr++ = tag & 0xFF;

    // Write length
    if (value_len < 0x80) {
        *ptr++ = value_len;
    } else {
        uint8_t lengthlen = 0;
        uint32_t tmp_len = value_len;
        while (tmp_len) {
            tmp_len >>= 8;
            lengthlen++;
        }
        *ptr++ = 0x80 | lengthlen;
        for (int i = lengthlen - 1; i >= 0; i--) {
            *ptr++ = (value_len >> (i * 8)) & 0xFF;
        }
    }

    // Write value
    if (value && value_len > 0) {
        memcpy(ptr, value, value_len);
        ptr += value_len;
    }

    *buffer_len = total_len;
}

int apdu_handle_connect(struct euicc_state *state) {
    euicc_state_init(state);
    
    // Load certificates from generated directory
    // Try multiple paths
    fprintf(stderr, "[v-euicc] Current working directory: ");
    char cwd[1024];
    if (getcwd(cwd, sizeof(cwd))) {
        fprintf(stderr, "%s\n", cwd);
    }

    if (euicc_state_load_certificates(state, "pySim/smdpp-data/generated") < 0) {
        if (euicc_state_load_certificates(state, "../pySim/smdpp-data/generated") < 0) {
            if (euicc_state_load_certificates(state, "../../pySim/smdpp-data/generated") < 0) {
                fprintf(stderr, "[v-euicc] Warning: Could not load certificates from any path\n");
            }
        }
    }
    
    return 0;
}

int apdu_handle_disconnect(struct euicc_state *state) {
    euicc_state_reset(state);
    return 0;
}

int apdu_handle_logic_channel_open(struct euicc_state *state, const uint8_t *aid, uint32_t aid_len) {
    // Verify AID matches expected ISD-R AID
    const uint8_t expected_aid[] = {0xA0, 0x00, 0x00, 0x05, 0x59, 0x10, 0x10, 0xFF,
                                    0xFF, 0xFF, 0xFF, 0x89, 0x00, 0x00, 0x01, 0x00};

    if (aid_len != sizeof(expected_aid) || memcmp(aid, expected_aid, aid_len) != 0) {
        fprintf(stderr, "Invalid AID received\n");
        return -1;
    }

    // Assign channel 1
    state->logic_channel = 1;
    memcpy(state->aid, aid, aid_len);
    state->aid_len = aid_len;

    return state->logic_channel;
}

int apdu_handle_logic_channel_close(struct euicc_state *state, uint8_t channel) {
    if (state->logic_channel == channel) {
        state->logic_channel = -1;
        state->aid_len = 0;
    }
    return 0;
}

// Build ProfileInstallationResult response
static int build_profile_installation_result(struct euicc_state *state, uint8_t **response, uint32_t *response_len) {
    // Build ProfileInstallationResult: BF37 {
    //     profileInstallationResultData (BF27 { ... }),
    //     euiccSignPIR (5F37)
    // }

    uint8_t pir_buf[512];
    uint8_t *pir_ptr = pir_buf;
    uint32_t pir_len = 0;

    // ProfileInstallationResultData (tag 0xBF27)
    uint8_t pird_buf[256];
    uint8_t *pird_ptr = pird_buf;
    uint32_t pird_len = 0;

    // transactionId (tag 0x80): use dummy transaction ID
    uint8_t txn_id[] = {0x80, 0x10, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
                       0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10};
    memcpy(pird_ptr, txn_id, sizeof(txn_id));
    pird_ptr += sizeof(txn_id);
    pird_len += sizeof(txn_id);

    // notificationMetadata (tag 0xBF2F)
    uint8_t notif_buf[64];
    uint8_t *notif_ptr = notif_buf;
    uint32_t notif_len = 0;

    // seqNumber (tag 0x80): increment sequence number
    uint8_t seq_num[] = {0x80, 0x01, state->notification_seq_number};
    memcpy(notif_ptr, seq_num, sizeof(seq_num));
    notif_ptr += sizeof(seq_num);
    notif_len += sizeof(seq_num);

    // profileManagementOperation (tag 0x81): INSTALL (0)
    uint8_t pm_op[] = {0x81, 0x01, 0x00};
    memcpy(notif_ptr, pm_op, sizeof(pm_op));
    notif_ptr += sizeof(pm_op);
    notif_len += sizeof(pm_op);

    // notificationAddress (tag 0x0C): use localhost
    const char *notif_addr = "localhost";
    uint8_t *addr_tlv = NULL;
    uint32_t addr_tlv_len = 0;
    build_tlv(&addr_tlv, &addr_tlv_len, 0x0C, (const uint8_t*)notif_addr, strlen(notif_addr));
    if (addr_tlv) {
        memcpy(notif_ptr, addr_tlv, addr_tlv_len);
        notif_len += addr_tlv_len;
        free(addr_tlv);
    }

    // Wrap notificationMetadata
    uint8_t *notif_tlv = NULL;
    uint32_t notif_tlv_len = 0;
    build_tlv(&notif_tlv, &notif_tlv_len, 0xBF2F, notif_buf, notif_len);
    if (notif_tlv) {
        memcpy(pird_ptr, notif_tlv, notif_tlv_len);
        pird_ptr += notif_tlv_len;
        pird_len += notif_tlv_len;
        free(notif_tlv);
    }

    // Add smdpOid: OID 2.999.10
    uint8_t smdp_oid[] = {0x06, 0x03, 0x88, 0x37, 0x0A}; // OBJECT IDENTIFIER
    memcpy(pird_ptr, smdp_oid, sizeof(smdp_oid));
    pird_ptr += sizeof(smdp_oid);
    pird_len += sizeof(smdp_oid);

    // Add finalResult (tag 0xA2) - SUCCESS
    uint8_t success_result_buf[64];
    uint8_t *success_ptr = success_result_buf;
    uint32_t success_len = 0;

    // SuccessResult SEQUENCE { aid, simaResponse }
    uint8_t dummy_aid[] = {0x4F, 0x10, 0xA0, 0x00, 0x00, 0x05, 0x59, 0x10, 0x10, 0xFF, 0xFF, 0xFF, 0xFF, 0x89, 0x00, 0x00, 0x10, 0x00};
    memcpy(success_ptr, dummy_aid, sizeof(dummy_aid));
    success_ptr += sizeof(dummy_aid);
    success_len += sizeof(dummy_aid);

    // simaResponse (tag 0x04): minimal response
    uint8_t sima[] = {0x04, 0x02, 0x90, 0x00};
    memcpy(success_ptr, sima, sizeof(sima));
    success_len += sizeof(sima);

    // SuccessResult SEQUENCE (0x30) - this is the CHOICE alternative encoding
    uint8_t *success_seq = NULL;
    uint32_t success_seq_len = 0;
    build_tlv(&success_seq, &success_seq_len, 0x30, success_result_buf, success_len);

    // Wrap in finalResult [2] CHOICE (0xA2) - CHOICE alternatives are encoded directly
    uint8_t *final_result_tlv = NULL;
    uint32_t final_result_tlv_len = 0;
    build_tlv(&final_result_tlv, &final_result_tlv_len, 0xA2, success_seq, success_seq_len);

    if (final_result_tlv) {
        memcpy(pird_ptr, final_result_tlv, final_result_tlv_len);
        pird_ptr += final_result_tlv_len;
        pird_len += final_result_tlv_len;
        free(final_result_tlv);
    }
    if (success_seq) {
        free(success_seq);
    }

    // Wrap ProfileInstallationResultData
    uint8_t *pird_tlv = NULL;
    uint32_t pird_tlv_len = 0;
    build_tlv(&pird_tlv, &pird_tlv_len, 0xBF27, pird_buf, pird_len);
    if (pird_tlv) {
        memcpy(pir_ptr, pird_tlv, pird_tlv_len);
        pir_ptr += pird_tlv_len;
        pir_len += pird_tlv_len;
        free(pird_tlv);
    }

    // euiccSignPIR (tag 0x5F37): dummy signature (32 bytes)
    uint8_t dummy_sig[34] = {0x5F, 0x37, 0x20};
    for (int i = 0; i < 32; i++) {
        dummy_sig[3 + i] = (uint8_t)(i & 0xFF);
    }
    memcpy(pir_ptr, dummy_sig, sizeof(dummy_sig));
    pir_len += sizeof(dummy_sig);

    // Wrap in ProfileInstallationResult (BF37)
    build_tlv(response, response_len, 0xBF37, pir_buf, pir_len);

    return 0;
}

// Process ES10x commands
static int process_es10x_command(struct euicc_state *state, uint8_t **response, uint32_t *response_len,
                                 const uint8_t *command, uint32_t command_len) {
    uint8_t *resp_body = NULL;
    uint32_t resp_body_len = 0;
    uint8_t status[] = {0x90, 0x00};

    // Parse command tag (assuming simple structure)
    if (command_len < 2) {
        return -1;
    }

    uint16_t tag = command[0];
    if ((tag & 0x1F) == 0x1F && command_len >= 2) {
        tag = (tag << 8) | command[1];
    }

    fprintf(stderr, "[v-euicc] ES10x command tag: %04X, len=%u\n", tag, command_len);
    
    // SGP.22 Section 3.1.3.3: lpac sends BPP commands wrapped in BF36
    // Handle BF36 wrapper by extracting the inner command
    if (tag == 0xBF36) {
        fprintf(stderr, "[v-euicc] BF36 wrapper detected (len=%u), extracting inner BPP command\n", command_len);
        
        // Dump first 20 bytes for debugging
        fprintf(stderr, "[v-euicc] BF36 data: ");
        for (uint32_t i = 0; i < command_len && i < 20; i++) {
            fprintf(stderr, "%02X ", command[i]);
        }
        fprintf(stderr, "...\n");
        
        // Skip BF36 tag (2 bytes) and length field to get to inner command
        const uint8_t *inner_cmd = command + 2;
        uint32_t inner_len = command_len - 2;
        
        // Parse length field (assuming < 128 bytes length, or extended length)
        if (inner_len > 0) {
            uint8_t len_byte = inner_cmd[0];
            fprintf(stderr, "[v-euicc] BF36 length byte: 0x%02X\n", len_byte);
            
            if (len_byte < 0x80) {
                // Short form: skip 1 byte
                inner_cmd += 1;
                inner_len -= 1;
                fprintf(stderr, "[v-euicc] BF36: Short length form\n");
            } else if (len_byte == 0x81) {
                // Long form with 1 length byte: skip 2 bytes
                inner_cmd += 2;
                inner_len -= 2;
                fprintf(stderr, "[v-euicc] BF36: Long length form (1 byte)\n");
            } else if (len_byte == 0x82) {
                // Long form with 2 length bytes: skip 3 bytes
                inner_cmd += 3;
                inner_len -= 3;
                fprintf(stderr, "[v-euicc] BF36: Long length form (2 bytes)\n");
            }
            
            // Now parse the actual inner command tag
            if (inner_len >= 2) {
                tag = inner_cmd[0];
                if ((tag & 0x1F) == 0x1F && inner_len >= 2) {
                    tag = (tag << 8) | inner_cmd[1];
                }
                
                // Update command pointer to inner command for processing
                command = inner_cmd;
                command_len = inner_len;
                
                fprintf(stderr, "[v-euicc] Inner BPP command tag: %04X, len=%u\n", tag, command_len);
                
                // Dump first 20 bytes of inner command
                fprintf(stderr, "[v-euicc] Inner cmd data: ");
                for (uint32_t i = 0; i < command_len && i < 20; i++) {
                    fprintf(stderr, "%02X ", command[i]);
                }
                fprintf(stderr, "...\n");
            } else {
                fprintf(stderr, "[v-euicc] BF36: Inner command too short (%u bytes)\n", inner_len);
            }
        } else {
            fprintf(stderr, "[v-euicc] BF36: Empty wrapper\n");
        }
    }

    switch (tag) {
    case 0xBF2E: { // GetEuiccChallengeRequest
        // Generate random 16-byte challenge
        for (int i = 0; i < 16; i++) {
            state->euicc_challenge[i] = (uint8_t)(rand() & 0xFF);
        }
        
        // Build response: BF2E { 80 <16-byte-challenge> }
        uint8_t *challenge_tlv = NULL;
        uint32_t challenge_tlv_len = 0;
        build_tlv(&challenge_tlv, &challenge_tlv_len, 0x80, state->euicc_challenge, 16);
        if (!challenge_tlv) {
            return -1;
        }
        
        build_tlv(&resp_body, &resp_body_len, 0xBF2E, challenge_tlv, challenge_tlv_len);
        free(challenge_tlv);
        break;
    }
    
    case 0xBF20: { // GetEuiccInfo1Request
        // Build EUICCInfo1: BF20 { 82 <svn> A9 {04 14 <pkid>} AA {04 14 <pkid>} }
        uint8_t info1_buf[256];
        uint8_t *info1_ptr = info1_buf;
        uint32_t info1_total_len = 0;
        
        // svn (tag 0x82): 2.2.0
        uint8_t *svn_tlv = NULL;
        uint32_t svn_tlv_len = 0;
        uint8_t svn[] = {0x02, 0x02, 0x00};
        build_tlv(&svn_tlv, &svn_tlv_len, 0x82, svn, sizeof(svn));
        if (svn_tlv) {
            memcpy(info1_ptr, svn_tlv, svn_tlv_len);
            info1_ptr += svn_tlv_len;
            info1_total_len += svn_tlv_len;
            free(svn_tlv);
        }
        
        // euiccCiPKIdListForVerification (tag 0xA9)
        // PKID from generated CI certificate: 3C:45:E5:F0:09:D0:2C:75:EC:F3:D7:FB:0B:63:FD:31:7C:DE:2C:4E
        uint8_t ci_pk[] = {0x04, 0x14, 0x3C, 0x45, 0xE5, 0xF0, 0x09, 0xD0, 0x2C, 0x75,
                          0xEC, 0xF3, 0xD7, 0xFB, 0x0B, 0x63, 0xFD, 0x31, 0x7C, 0xDE, 0x2C, 0x4E};
        uint8_t *ci_pk_ver_tlv = NULL;
        uint32_t ci_pk_ver_tlv_len = 0;
        build_tlv(&ci_pk_ver_tlv, &ci_pk_ver_tlv_len, 0xA9, ci_pk, sizeof(ci_pk));
        if (ci_pk_ver_tlv) {
            memcpy(info1_ptr, ci_pk_ver_tlv, ci_pk_ver_tlv_len);
            info1_ptr += ci_pk_ver_tlv_len;
            info1_total_len += ci_pk_ver_tlv_len;
            free(ci_pk_ver_tlv);
        }
        
        // euiccCiPKIdListForSigning (tag 0xAA)
        uint8_t *ci_pk_sign_tlv = NULL;
        uint32_t ci_pk_sign_tlv_len = 0;
        build_tlv(&ci_pk_sign_tlv, &ci_pk_sign_tlv_len, 0xAA, ci_pk, sizeof(ci_pk));
        if (ci_pk_sign_tlv) {
            memcpy(info1_ptr, ci_pk_sign_tlv, ci_pk_sign_tlv_len);
            info1_total_len += ci_pk_sign_tlv_len;
            free(ci_pk_sign_tlv);
        }
        
        build_tlv(&resp_body, &resp_body_len, 0xBF20, info1_buf, info1_total_len);
        break;
    }
    
    case 0xBF3E: { // GetEuiccDataRequest (GetEID)
        // Build response: BF3E 12 5A 10 <16-byte-eid> 9000
        uint8_t eid_bin[16];
        if (euicc_hexutil_hex2bin(eid_bin, sizeof(eid_bin), state->eid) != 16) {
            return -1;
        }

        uint8_t *eid_tlv = NULL;
        uint32_t eid_tlv_len = 0;
        build_tlv(&eid_tlv, &eid_tlv_len, 0x5A, eid_bin, sizeof(eid_bin));
        if (!eid_tlv) {
            return -1;
        }

        build_tlv(&resp_body, &resp_body_len, 0xBF3E, eid_tlv, eid_tlv_len);
        free(eid_tlv);
        break;
    }

    case 0xBF3C: { // EuiccConfiguredAddressesRequest
        // Build response with rootDsAddress
        uint8_t addr_tlv_buf[256];
        uint8_t *addr_ptr = addr_tlv_buf;
        uint32_t addr_total_len = 0;

        // Add rootDsAddress (tag 0x81)
        uint8_t *smds_tlv = NULL;
        uint32_t smds_tlv_len = 0;
        build_tlv(&smds_tlv, &smds_tlv_len, 0x81, (const uint8_t *)state->root_smds, strlen(state->root_smds));
        if (!smds_tlv) {
            return -1;
        }

        memcpy(addr_ptr, smds_tlv, smds_tlv_len);
        addr_total_len = smds_tlv_len;
        free(smds_tlv);

        // If defaultDpAddress exists, add it (tag 0x80)
        if (strlen(state->default_smdp) > 0) {
            uint8_t *smdp_tlv = NULL;
            uint32_t smdp_tlv_len = 0;
            build_tlv(&smdp_tlv, &smdp_tlv_len, 0x80, (const uint8_t *)state->default_smdp, strlen(state->default_smdp));
            if (smdp_tlv) {
                // Insert at beginning
                memmove(addr_tlv_buf + smdp_tlv_len, addr_tlv_buf, addr_total_len);
                memcpy(addr_tlv_buf, smdp_tlv, smdp_tlv_len);
                addr_total_len += smdp_tlv_len;
                free(smdp_tlv);
            }
        }

        build_tlv(&resp_body, &resp_body_len, 0xBF3C, addr_tlv_buf, addr_total_len);
        break;
    }

    case 0xBF38: { // AuthenticateServerRequest
        // This is the most complex command - implements mutual authentication
        // Phase 1: Mock implementation with minimal parsing
        // Phase 2: Real crypto with signature verification and generation
        
        // Parse request structure (simplified - just extract key fields)
        // AuthenticateServerRequest ::= BF38 {
        //     serverSigned1, serverSignature1, euiccCiPKIdToBeUsed,
        //     serverCertificate, ctxParams1
        // }
        
        // For mock: we need to extract transactionID and build response
        // Real implementation would verify signatures and certificates
        
        // Extract transactionID, serverChallenge, serverAddress, and matchingID from request
        const uint8_t *ptr = command;
        uint32_t remaining = command_len;

        // Clear matching ID first
        memset(state->matching_id, 0, sizeof(state->matching_id));

        // Default server address
        const char *server_addr = "localhost";
        uint8_t server_addr_len = 9;

        // Find serverSigned1 (tag 0x30) to extract transactionID, serverChallenge, and serverAddress
        while (remaining > 2) {
            if (ptr[0] == 0x30) {
                uint8_t len = ptr[1];
                if (len < 0x80) {
                    const uint8_t *inner_ptr = ptr + 2;
                    uint32_t inner_remaining = len;

                    while (inner_remaining > 2) {
                        uint8_t tag = inner_ptr[0];
                        uint8_t field_len = inner_ptr[1];

                        if (field_len >= 0x80 || inner_remaining < 2 + field_len) {
                            break;
                        }

                        if (tag == 0x80 && field_len <= 16) {
                            memcpy(state->transaction_id, inner_ptr + 2, field_len);
                            state->transaction_id_len = field_len;
                        } else if (tag == 0x84 && field_len == 16) {
                            memcpy(state->server_challenge, inner_ptr + 2, 16);
                        } else if (tag == 0x83 && field_len > 0 && field_len < 256) {
                            // serverAddress found
                            server_addr = (const char*)(inner_ptr + 2);
                            server_addr_len = field_len;
                            LOG_V_EUICC_INFO("Extracted serverAddress: %.*s (len=%u)", server_addr_len, server_addr, server_addr_len);
                        }

                        inner_ptr += 2 + field_len;
                        inner_remaining -= 2 + field_len;
                    }
                }
                break;
            }
            ptr++;
            remaining--;
        }
        
        // Extract matchingID from ctxParams1 (tag 0xA0)
        // ctxParams1 is the last field in AuthenticateServerRequest
        ptr = command;
        remaining = command_len;
        int found_ctx = 0;
        while (remaining > 2) {
            if (ptr[0] == 0xA0) {
                fprintf(stderr, "[v-euicc] Found ctxParams1 at offset %lu\n", ptr - command);
                uint8_t len = ptr[1];
                if (len < 0x80) {
                    // Look for matchingId (tag 0x80) inside ctxParams1
                    const uint8_t *ctx_ptr = ptr + 2;
                    uint32_t ctx_remaining = len;
                    
                    while (ctx_remaining > 2) {
                        uint8_t tag = ctx_ptr[0];
                        uint8_t field_len = ctx_ptr[1];
                        
                        fprintf(stderr, "[v-euicc] ctxParams1 field: tag=%02X len=%u\n", tag, field_len);
                        
                        if (field_len >= 0x80 || ctx_remaining < 2 + field_len) {
                            break;
                        }
                        
                        if (tag == 0x80 && field_len > 0 && field_len < sizeof(state->matching_id)) {
                            // matchingId found - it's a UTF8String
                            memcpy(state->matching_id, ctx_ptr + 2, field_len);
                            state->matching_id[field_len] = '\0';
                            LOG_V_EUICC_INFO("Extracted matchingID: %s", state->matching_id);
                            found_ctx = 1;
                            break;
                        }
                        
                        ctx_ptr += 2 + field_len;
                        ctx_remaining -= 2 + field_len;
                    }
                }
                if (found_ctx) break;
            }
            ptr++;
            remaining--;
        }
        
        // Build mock AuthenticateServerResponse
        // AuthenticateServerResponse ::= BF38 { A0 {
        //     euiccSigned1, euiccSignature1, euiccCertificate, eumCertificate
        // }}
        
        uint8_t auth_resp_buf[2048];
        uint8_t *auth_resp_ptr = auth_resp_buf;
        uint32_t auth_resp_len = 0;
        
        // Build euiccSigned1 (tag 0x30)
        uint8_t euicc_signed1_buf[512];
        uint8_t *signed1_ptr = euicc_signed1_buf;
        uint32_t signed1_len = 0;
        
        // Add transactionID (tag 0x80)
        uint8_t *tid_tlv = NULL;
        uint32_t tid_tlv_len = 0;
        build_tlv(&tid_tlv, &tid_tlv_len, 0x80, state->transaction_id, state->transaction_id_len);
        if (tid_tlv) {
            memcpy(signed1_ptr, tid_tlv, tid_tlv_len);
            signed1_ptr += tid_tlv_len;
            signed1_len += tid_tlv_len;
            free(tid_tlv);
        }
        
        // Add serverAddress (tag 0x83)
        uint8_t *addr_tlv = NULL;
        uint32_t addr_tlv_len = 0;
        build_tlv(&addr_tlv, &addr_tlv_len, 0x83, (const uint8_t *)server_addr, server_addr_len);
        if (addr_tlv) {
            memcpy(signed1_ptr, addr_tlv, addr_tlv_len);
            signed1_ptr += addr_tlv_len;
            signed1_len += addr_tlv_len;
            free(addr_tlv);
        }
        
        // Add serverChallenge (tag 0x84) - echo back from request
        uint8_t *schall_tlv = NULL;
        uint32_t schall_tlv_len = 0;
        build_tlv(&schall_tlv, &schall_tlv_len, 0x84, state->server_challenge, 16);
        if (schall_tlv) {
            memcpy(signed1_ptr, schall_tlv, schall_tlv_len);
            signed1_ptr += schall_tlv_len;
            signed1_len += schall_tlv_len;
            free(schall_tlv);
        }
        
        // Add euiccInfo2 (tag 0xBF22) - minimal version for compatibility
        uint8_t *info2_data = NULL;
        uint32_t info2_data_len = 0;
        if (build_euiccinfo2(&info2_data, &info2_data_len) < 0) {
            return -1;
        }

        uint8_t *info2_tlv = NULL;
        uint32_t info2_tlv_len = 0;
        build_tlv(&info2_tlv, &info2_tlv_len, 0xBF22, info2_data, info2_data_len);
        
        // Debug: Print euiccInfo2 with BF22 wrapper
        fprintf(stderr, "DEBUG: euiccInfo2 with BF22 wrapper (%u bytes):\n", info2_tlv_len);
        for (uint32_t i = 0; i < info2_tlv_len; i++) {
            fprintf(stderr, "%02x", info2_tlv[i]);
        }
        fprintf(stderr, "\n");
        
        free(info2_data);

        if (info2_tlv) {
            memcpy(signed1_ptr, info2_tlv, info2_tlv_len);
            signed1_ptr += info2_tlv_len;
            signed1_len += info2_tlv_len;
            free(info2_tlv);
        }
        
        // Add ctxParams1 (tag 0xA0) - must include matchingID (if present) and deviceInfo
        uint8_t ctx_buf[256];
        uint8_t *ctx_ptr = ctx_buf;
        uint32_t ctx_len = 0;
        
        // Add matchingID (tag 0x80) if we have one
        if (strlen(state->matching_id) > 0) {
            uint8_t *mid_tlv = NULL;
            uint32_t mid_tlv_len = 0;
            build_tlv(&mid_tlv, &mid_tlv_len, 0x80, (const uint8_t*)state->matching_id, strlen(state->matching_id));
            if (mid_tlv) {
                memcpy(ctx_ptr, mid_tlv, mid_tlv_len);
                ctx_ptr += mid_tlv_len;
                ctx_len += mid_tlv_len;
                free(mid_tlv);
            }
        }
        
        // Build deviceInfo (tag 0xA1)
        uint8_t dev_info_buf[48];
        uint8_t *dev_ptr = dev_info_buf;
        uint32_t dev_len = 0;
        
        // tac (tag 0x80): 4 bytes
        uint8_t tac[] = {0x80, 0x04, 0x35, 0x29, 0x06, 0x11};
        memcpy(dev_ptr, tac, sizeof(tac));
        dev_ptr += sizeof(tac);
        dev_len += sizeof(tac);
        
        // deviceCapabilities (tag 0xA1) - add at least one capability
        uint8_t dev_cap_buf[16];
        uint8_t *dev_cap_ptr = dev_cap_buf;
        uint32_t dev_cap_len = 0;
        
        // eutranSupportedRelease (tag 0x85): 15.0.0
        uint8_t eutran_rel[] = {0x85, 0x03, 0x0F, 0x00, 0x00};
        memcpy(dev_cap_ptr, eutran_rel, sizeof(eutran_rel));
        dev_cap_len += sizeof(eutran_rel);
        
        uint8_t *dev_cap_tlv = NULL;
        uint32_t dev_cap_tlv_len = 0;
        build_tlv(&dev_cap_tlv, &dev_cap_tlv_len, 0xA1, dev_cap_buf, dev_cap_len);
        if (dev_cap_tlv) {
            memcpy(dev_ptr, dev_cap_tlv, dev_cap_tlv_len);
            dev_len += dev_cap_tlv_len;
            free(dev_cap_tlv);
        }
        
        // Wrap deviceInfo in tag 0xA1
        uint8_t *dev_info_tlv = NULL;
        uint32_t dev_info_tlv_len = 0;
        build_tlv(&dev_info_tlv, &dev_info_tlv_len, 0xA1, dev_info_buf, dev_len);
        if (dev_info_tlv) {
            memcpy(ctx_ptr, dev_info_tlv, dev_info_tlv_len);
            ctx_ptr += dev_info_tlv_len;
            ctx_len += dev_info_tlv_len;
            free(dev_info_tlv);
        }
        
        // Wrap in ctxParamsForCommonAuthentication (tag 0xA0)
        uint8_t *ctx_tlv = NULL;
        uint32_t ctx_tlv_len = 0;
        build_tlv(&ctx_tlv, &ctx_tlv_len, 0xA0, ctx_buf, ctx_len);
        if (ctx_tlv) {
            memcpy(signed1_ptr, ctx_tlv, ctx_tlv_len);
            signed1_len += ctx_tlv_len;
            free(ctx_tlv);
        }
        
        // Wrap euiccSigned1 in SEQUENCE (tag 0x30)
        uint8_t *euicc_signed1_tlv = NULL;
        uint32_t euicc_signed1_tlv_len = 0;
        build_tlv(&euicc_signed1_tlv, &euicc_signed1_tlv_len, 0x30, euicc_signed1_buf, signed1_len);
        if (!euicc_signed1_tlv) {
            return -1;
        }
        
        
        // Sign the complete euiccSigned1 TLV (IMPORTANT: sign the TLV, not the raw buffer)
        uint8_t *real_signature = NULL;
        uint32_t real_signature_len = 0;
        
        if (state->euicc_private_key_len > 0 && state->euicc_private_key) {
            EVP_PKEY *pkey = (EVP_PKEY*)state->euicc_private_key;
            
            // Sign the complete euiccSigned1 TLV structure
            if (ecdsa_sign(euicc_signed1_tlv, euicc_signed1_tlv_len, pkey, &real_signature, &real_signature_len) < 0) {
                fprintf(stderr, "[v-euicc] ECDSA signing failed\n");
                free(euicc_signed1_tlv);
                return -1;
            }
            
            LOG_V_EUICC_INFO("AuthenticateServer: Real ECDSA signature generated (%u bytes)", real_signature_len);
        } else {
            fprintf(stderr, "[v-euicc] ERROR: Private key not loaded, cannot sign\n");
            free(euicc_signed1_tlv);
            return -1;
        }
        
        // Now add euiccSigned1 to response
        memcpy(auth_resp_ptr, euicc_signed1_tlv, euicc_signed1_tlv_len);
        auth_resp_ptr += euicc_signed1_tlv_len;
        auth_resp_len += euicc_signed1_tlv_len;
        free(euicc_signed1_tlv);
        
        uint8_t *sig_tlv = NULL;
        uint32_t sig_tlv_len = 0;
        build_tlv(&sig_tlv, &sig_tlv_len, 0x5F37, real_signature, real_signature_len);
        free(real_signature);  // Free the signature buffer after building TLV
        
        if (sig_tlv) {
            memcpy(auth_resp_ptr, sig_tlv, sig_tlv_len);
            auth_resp_ptr += sig_tlv_len;
            auth_resp_len += sig_tlv_len;
            free(sig_tlv);
        }
        
        // Add euiccCertificate (tag 0x30) - use loaded certificate
        if (state->euicc_cert && state->euicc_cert_len > 0) {
            // Certificate is already in DER format with tag 0x30, just append it
            memcpy(auth_resp_ptr, state->euicc_cert, state->euicc_cert_len);
            auth_resp_ptr += state->euicc_cert_len;
            auth_resp_len += state->euicc_cert_len;
        } else {
            fprintf(stderr, "[v-euicc] Warning: eUICC certificate not loaded\n");
        }

        // Add eumCertificate (tag 0x30) - use loaded certificate
        if (state->eum_cert && state->eum_cert_len > 0) {
            // Certificate is already in DER format with tag 0x30, just append it
            memcpy(auth_resp_ptr, state->eum_cert, state->eum_cert_len);
            auth_resp_len += state->eum_cert_len;
        } else {
            fprintf(stderr, "[v-euicc] Warning: EUM certificate not loaded\n");
        }
        
        // FIX: With AUTOMATIC TAGS, SEQUENCE types don't get explicit tags
        // authenticateResponseOk is SEQUENCE, so just wrap content with A0, then BF38
        // Structure: BF38 { A0 { AuthenticateResponseOk content } }

        // Wrap in A0 for the CHOICE alternative [0]
        uint8_t *auth_choice_tlv = NULL;
        uint32_t auth_choice_tlv_len = 0;
        build_tlv(&auth_choice_tlv, &auth_choice_tlv_len, 0xA0, auth_resp_buf, auth_resp_len);
        if (!auth_choice_tlv) {
            return -1;
        }

        // Final response: BF38 { A0 { ... } }
        build_tlv(&resp_body, &resp_body_len, 0xBF38, auth_choice_tlv, auth_choice_tlv_len);
        free(auth_choice_tlv);

    LOG_V_EUICC_INFO("AuthenticateServer: Response generated with real ECDSA signature (Phase 2)");
    break;
    }
    
    case 0xBF21: { // PrepareDownloadRequest
        // PrepareDownloadRequest ::= BF21 {
        //     smdpSigned2 (30), smdpSignature2 (5F37), [hashCC (04)], smdpCertificate (30)
        // }
        
        fprintf(stderr, "[v-euicc] PrepareDownloadRequest received\n");
        
        // Extract smdpSigned2 to get transactionID
        const uint8_t *ptr = command;
        uint32_t remaining = command_len;
        
        // Find smdpSigned2 (tag 0x30)
        while (remaining > 2) {
            if (ptr[0] == 0x30) {
                uint8_t len = ptr[1];
                if (len < 0x80 && remaining >= 2 + len) {
                    // Look for transactionID (tag 0x80) inside smdpSigned2
                    const uint8_t *inner = ptr + 2;
                    uint32_t inner_remaining = len;
                    
                    while (inner_remaining > 2) {
                        if (inner[0] == 0x80) {
                            uint8_t tid_len = inner[1];
                            if (tid_len <= 16 && inner_remaining >= 2 + tid_len) {
                                memcpy(state->transaction_id, inner + 2, tid_len);
                                state->transaction_id_len = tid_len;
                                fprintf(stderr, "[v-euicc] Extracted transactionID: %u bytes\n", tid_len);
                                break;
                            }
                        }
                        uint8_t skip = inner[1];
                        if (skip >= 0x80) break;
                        inner += 2 + skip;
                        inner_remaining -= 2 + skip;
                    }
                }
                break;
            }
            ptr++;
            remaining--;
        }
        
        // Extract smdpSignature2 from the request for signing (osmo-smdpp format)
        uint8_t *smdp_signature2_do = NULL;
        uint32_t smdp_signature2_do_len = 0;

        // Find smdpSignature2 (tag 0x5F37) by scanning for the pattern
        for (uint32_t i = 0; i < command_len - 3; i++) {
            if (command[i] == 0x5F && command[i+1] == 0x37) {
                uint8_t len = command[i+2];
                if (len < 0x80 && i + 3 + len <= command_len) {
                    // Extract just the signature bytes and construct osmo-smdpp format: b'\x5f\x37\x40' + sig_bytes
                    smdp_signature2_do_len = 3 + len;  // \x5f\x37\x40 + sig_bytes
                    smdp_signature2_do = malloc(smdp_signature2_do_len);
                    if (smdp_signature2_do) {
                        smdp_signature2_do[0] = 0x5F;
                        smdp_signature2_do[1] = 0x37;
                        smdp_signature2_do[2] = 0x40;  // osmo-smdpp hardcodes this
                        memcpy(smdp_signature2_do + 3, &command[i+3], len);
                        fprintf(stderr, "[v-euicc] Extracted smdpSignature2: %u bytes at offset %u\n", len, i);
                    }
                    break;
                }
            }
        }

        // Phase A: Skip signature verification, just build response
        // Build euiccSigned2 (SEQUENCE tag 0x30)
        // Buffer needs to hold: transactionID (~18) + euiccOtpk (~68) + smdpOid (~10) + ML-KEM PK (~1187) = ~1283 bytes
        uint8_t euicc_signed2_buf[2048];  // Increased from 256 to support PQC
        uint8_t *signed2_ptr = euicc_signed2_buf;
        uint32_t signed2_len = 0;
        
        // Add transactionID (tag 0x80)
        uint8_t *tid_tlv = NULL;
        uint32_t tid_tlv_len = 0;
        build_tlv(&tid_tlv, &tid_tlv_len, 0x80, state->transaction_id, state->transaction_id_len);
        if (tid_tlv) {
            memcpy(signed2_ptr, tid_tlv, tid_tlv_len);
            signed2_ptr += tid_tlv_len;
            signed2_len += tid_tlv_len;
            free(tid_tlv);
        }
        
        // Add euiccOtpk (tag 0x5F49 = APPLICATION 73)
        // Generate a real EC key pair and use the public key
        // SGP.22 Section 3.1.3.2: eUICC generates or reuses otPK.EUICC.ECKA key pair
        EVP_PKEY *otpk_keypair = generate_ec_keypair();
        uint8_t *euicc_otpk = NULL;
        uint32_t euicc_otpk_len = 0;

        if (otpk_keypair) {
            euicc_otpk = extract_ec_public_key_uncompressed(otpk_keypair, &euicc_otpk_len);
            if (!euicc_otpk || euicc_otpk_len != 65) {
                fprintf(stderr, "[v-euicc] Failed to extract euiccOtpk public key\n");
                if (euicc_otpk) free(euicc_otpk);
                EVP_PKEY_free(otpk_keypair);
                return -1;
            } else {
                fprintf(stderr, "[v-euicc] Generated valid euiccOtpk: ");
                for (uint32_t i = 0; i < euicc_otpk_len && i < 8; i++) {
                    fprintf(stderr, "%02x ", euicc_otpk[i]);
                }
                fprintf(stderr, "...\n");
            }
        } else {
            fprintf(stderr, "[v-euicc] Failed to generate euiccOtpk keypair\n");
            return -1;
        }

        uint8_t *otpk_tlv = NULL;
        uint32_t otpk_tlv_len = 0;
        build_tlv(&otpk_tlv, &otpk_tlv_len, 0x5F49, euicc_otpk, euicc_otpk_len);
        if (otpk_tlv) {
            memcpy(signed2_ptr, otpk_tlv, otpk_tlv_len);
            signed2_ptr += otpk_tlv_len;
            signed2_len += otpk_tlv_len;
            free(otpk_tlv);
        }

        // Store the ephemeral key pair in state for session key derivation (SGP.22 Section 3.1.3.3)
        // This is required for InitialiseSecureChannel to derive session keys
        free(state->euicc_otpk);
        state->euicc_otpk = euicc_otpk;  // Transfer ownership
        state->euicc_otpk_len = euicc_otpk_len;
        
        // Extract and store the private key for ECKA
        free(state->euicc_otsk);
        state->euicc_otsk = extract_ec_private_key(otpk_keypair, &state->euicc_otsk_len);
        if (!state->euicc_otsk || state->euicc_otsk_len != 32) {
            fprintf(stderr, "[v-euicc] Failed to extract euiccOtsk private key\n");
            EVP_PKEY_free(otpk_keypair);
            return -1;
        }
        
        fprintf(stderr, "[v-euicc] Stored otPK.EUICC.ECKA (%u bytes) and otSK.EUICC.ECKA (%u bytes)\n",
                state->euicc_otpk_len, state->euicc_otsk_len);
        
        EVP_PKEY_free(otpk_keypair);
        
#ifdef ENABLE_PQC
        // Generate ML-KEM-768 keypair if PQC is supported
        if (state->pqc_caps.mlkem768_supported) {
            fprintf(stderr, "[v-euicc] Generating ML-KEM-768 keypair for hybrid mode...\n");
            
            if (generate_mlkem_keypair(&state->euicc_pk_kem, &state->euicc_pk_kem_len,
                                      &state->euicc_sk_kem, &state->euicc_sk_kem_len) == 0) {
                state->pqc_caps.hybrid_mode_active = true;
                fprintf(stderr, "[v-euicc] ML-KEM-768 keypair generated: pk=%u bytes, sk=%u bytes\n",
                       state->euicc_pk_kem_len, state->euicc_sk_kem_len);
                
                // Detailed PQC demo logging
                fprintf(stderr, "[PQC-DEMO] PrepareDownload: ML-KEM-768 keypair generated\n");
                fprintf(stderr, "[PQC-DEMO]   Public Key Size: %u bytes (expected 1184)\n", state->euicc_pk_kem_len);
                fprintf(stderr, "[PQC-DEMO]   Secret Key Size: %u bytes (expected 2400)\n", state->euicc_sk_kem_len);
                fprintf(stderr, "[PQC-DEMO]   First 32 bytes of PK: ");
                for (int i = 0; i < 32 && i < state->euicc_pk_kem_len; i++) {
                    fprintf(stderr, "%02x", state->euicc_pk_kem[i]);
                }
                fprintf(stderr, "...\n");
                
                // Add ML-KEM public key to response (tag 0x5F4A = APPLICATION 74, custom extension)
                fprintf(stderr, "[v-euicc] signed2_len BEFORE adding ML-KEM: %u bytes\n", signed2_len);
                uint8_t *pk_kem_tlv = NULL;
                uint32_t pk_kem_tlv_len = 0;
                build_tlv(&pk_kem_tlv, &pk_kem_tlv_len, 0x5F4A, state->euicc_pk_kem, state->euicc_pk_kem_len);
                if (pk_kem_tlv) {
                    fprintf(stderr, "[v-euicc] ML-KEM TLV built: %u bytes (key=%u + TLV overhead)\n", pk_kem_tlv_len, state->euicc_pk_kem_len);
                    memcpy(signed2_ptr, pk_kem_tlv, pk_kem_tlv_len);
                    signed2_ptr += pk_kem_tlv_len;
                    signed2_len += pk_kem_tlv_len;
                    free(pk_kem_tlv);
                    fprintf(stderr, "[v-euicc] signed2_len AFTER adding ML-KEM: %u bytes\n", signed2_len);
                    fprintf(stderr, "[v-euicc] Added ML-KEM public key to PrepareDownload response\n");
                    fprintf(stderr, "[PQC-DEMO] PrepareDownload: Added tag 0x5F4A (ML-KEM public key) to response\n");
                } else {
                    fprintf(stderr, "[v-euicc] ERROR: Failed to build ML-KEM TLV!\n");
                }
            } else {
                fprintf(stderr, "[v-euicc] Warning: ML-KEM keypair generation failed, falling back to classical mode\n");
                state->pqc_caps.hybrid_mode_active = false;
            }
        }
#endif
        
        // Wrap in SEQUENCE (tag 0x30)
        uint8_t *euicc_signed2_tlv = NULL;
        uint32_t euicc_signed2_tlv_len = 0;
        fprintf(stderr, "[v-euicc] Building SEQUENCE wrapper for %u bytes of content\n", signed2_len);
        build_tlv(&euicc_signed2_tlv, &euicc_signed2_tlv_len, 0x30, euicc_signed2_buf, signed2_len);
        if (!euicc_signed2_tlv) {
            return -1;
        }
        fprintf(stderr, "[v-euicc] euiccSigned2 TLV complete: %u bytes total (content=%u + TLV overhead)\n", euicc_signed2_tlv_len, signed2_len);
        
        // Sign euiccSigned2 + smdpSignature2 according to SGP.22
        uint8_t *signature = NULL;
        uint32_t signature_len = 0;

        if (state->euicc_private_key_len > 0 && state->euicc_private_key) {
            EVP_PKEY *pkey = (EVP_PKEY*)state->euicc_private_key;

            // Sign euiccSigned2 + smdpSignature2_do (osmo-smdpp format)
            uint32_t combined_len = euicc_signed2_tlv_len;
            if (smdp_signature2_do) {
                combined_len += smdp_signature2_do_len;
                fprintf(stderr, "[v-euicc] Signing euiccSigned2 + smdpSignature2_do (%u + %u bytes)\n", euicc_signed2_tlv_len, smdp_signature2_do_len);
            } else {
                fprintf(stderr, "[v-euicc] WARNING: smdpSignature2 not found\n");
            }

            uint8_t *combined_data = malloc(combined_len);
            if (!combined_data) {
                free(euicc_signed2_tlv);
                free(smdp_signature2_do);
                return -1;
            }
            memcpy(combined_data, euicc_signed2_tlv, euicc_signed2_tlv_len);
            if (smdp_signature2_do) {
                memcpy(combined_data + euicc_signed2_tlv_len, smdp_signature2_do, smdp_signature2_do_len);
            }

            if (ecdsa_sign(combined_data, combined_len, pkey, &signature, &signature_len) < 0) {
                fprintf(stderr, "[v-euicc] PrepareDownload: ECDSA signing failed\n");
                free(combined_data);
                free(euicc_signed2_tlv);
                free(smdp_signature2_do);
                return -1;
            }
            fprintf(stderr, "[v-euicc] PrepareDownload: Signature generated (%u bytes) over %u bytes\n", signature_len, combined_len);
            free(combined_data);
        } else {
            free(euicc_signed2_tlv);
            free(smdp_signature2_do);
            return -1;
        }

        free(smdp_signature2_do);
        
        // Build PrepareDownloadResponse: BF21 { A0 { euiccSigned2, euiccSignature2 } }
        // Buffer needs to hold: euiccSigned2 TLV (~1290) + signature TLV (~67) = ~1357 bytes
        uint8_t prep_resp_buf[2048];  // Increased from 512 to support PQC
        uint8_t *prep_ptr = prep_resp_buf;
        uint32_t prep_len = 0;
        
        memcpy(prep_ptr, euicc_signed2_tlv, euicc_signed2_tlv_len);
        prep_ptr += euicc_signed2_tlv_len;
        prep_len += euicc_signed2_tlv_len;
        free(euicc_signed2_tlv);
        
        // Add signature (tag 0x5F37)
        uint8_t *sig_tlv = NULL;
        uint32_t sig_tlv_len = 0;
        build_tlv(&sig_tlv, &sig_tlv_len, 0x5F37, signature, signature_len);
        free(signature);
        
        if (sig_tlv) {
            memcpy(prep_ptr, sig_tlv, sig_tlv_len);
            prep_len += sig_tlv_len;
            free(sig_tlv);
        }
        
        // Wrap in downloadResponseOk (tag 0xA0)
        uint8_t *resp_ok_tlv = NULL;
        uint32_t resp_ok_tlv_len = 0;
        build_tlv(&resp_ok_tlv, &resp_ok_tlv_len, 0xA0, prep_resp_buf, prep_len);
        if (!resp_ok_tlv) {
            return -1;
        }
        
        // Final response: BF21 { A0 { ... } }
        build_tlv(&resp_body, &resp_body_len, 0xBF21, resp_ok_tlv, resp_ok_tlv_len);
        free(resp_ok_tlv);
        
        fprintf(stderr, "[v-euicc] PrepareDownload: Response generated (%u bytes total)\n", resp_body_len);
        fprintf(stderr, "[METRICS] PrepareDownloadResponse: %u bytes\n", resp_body_len);
        break;
    }
    
    case 0xBF22: { // GetEuiccInfo2Request
        // Build minimal EUICCInfo2 response
        uint8_t info2_buf[512];
        uint8_t *info_ptr = info2_buf;
        uint32_t info_total_len = 0;

        // profileVersion (tag 0x81): 2.1.0
        uint8_t *profile_ver_tlv = NULL;
        uint32_t profile_ver_tlv_len = 0;
        uint8_t profile_ver[] = {0x02, 0x01, 0x00};
        build_tlv(&profile_ver_tlv, &profile_ver_tlv_len, 0x81, profile_ver, sizeof(profile_ver));
        if (profile_ver_tlv) {
            memcpy(info_ptr, profile_ver_tlv, profile_ver_tlv_len);
            info_ptr += profile_ver_tlv_len;
            info_total_len += profile_ver_tlv_len;
            free(profile_ver_tlv);
        }

        // svn (tag 0x82): 2.2.0
        uint8_t *svn_tlv = NULL;
        uint32_t svn_tlv_len = 0;
        uint8_t svn[] = {0x02, 0x02, 0x00};
        build_tlv(&svn_tlv, &svn_tlv_len, 0x82, svn, sizeof(svn));
        if (svn_tlv) {
            memcpy(info_ptr, svn_tlv, svn_tlv_len);
            info_ptr += svn_tlv_len;
            info_total_len += svn_tlv_len;
            free(svn_tlv);
        }

        // euiccFirmwareVer (tag 0x83): 1.0.0
        uint8_t *fw_ver_tlv = NULL;
        uint32_t fw_ver_tlv_len = 0;
        uint8_t fw_ver[] = {0x01, 0x00, 0x00};
        build_tlv(&fw_ver_tlv, &fw_ver_tlv_len, 0x83, fw_ver, sizeof(fw_ver));
        if (fw_ver_tlv) {
            memcpy(info_ptr, fw_ver_tlv, fw_ver_tlv_len);
            info_ptr += fw_ver_tlv_len;
            info_total_len += fw_ver_tlv_len;
            free(fw_ver_tlv);
        }

        // extCardResource (tag 0x84)
        uint8_t ext_card_buf[32];
        uint8_t *ext_card_ptr = ext_card_buf;
        uint32_t ext_card_len = 0;

        // installedApplication (tag 0x81): 0
        uint8_t installed_app[] = {0x81, 0x01, 0x00};
        memcpy(ext_card_ptr, installed_app, sizeof(installed_app));
        ext_card_ptr += sizeof(installed_app);
        ext_card_len += sizeof(installed_app);

        // freeNonVolatileMemory (tag 0x82): 291666 (0x047352)
        uint8_t free_nv[] = {0x82, 0x03, 0x04, 0x73, 0x52};
        memcpy(ext_card_ptr, free_nv, sizeof(free_nv));
        ext_card_ptr += sizeof(free_nv);
        ext_card_len += sizeof(free_nv);

        // freeVolatileMemory (tag 0x83): 5970 (0x1752)
        uint8_t free_v[] = {0x83, 0x02, 0x17, 0x52};
        memcpy(ext_card_ptr, free_v, sizeof(free_v));
        ext_card_len += sizeof(free_v);

        uint8_t *ext_card_tlv = NULL;
        uint32_t ext_card_tlv_len = 0;
        build_tlv(&ext_card_tlv, &ext_card_tlv_len, 0x84, ext_card_buf, ext_card_len);
        if (ext_card_tlv) {
            memcpy(info_ptr, ext_card_tlv, ext_card_tlv_len);
            info_ptr += ext_card_tlv_len;
            info_total_len += ext_card_tlv_len;
            free(ext_card_tlv);
        }

        // uiccCapability (tag 0x85): BIT STRING - simplified to avoid parsing issues
        uint8_t uicc_cap[] = {0x00};  // Just unused bits byte = 0
        uint8_t *uicc_cap_tlv = NULL;
        uint32_t uicc_cap_tlv_len = 0;
        build_tlv(&uicc_cap_tlv, &uicc_cap_tlv_len, 0x85, uicc_cap, sizeof(uicc_cap));
        if (uicc_cap_tlv) {
            memcpy(info_ptr, uicc_cap_tlv, uicc_cap_tlv_len);
            info_ptr += uicc_cap_tlv_len;
            info_total_len += uicc_cap_tlv_len;
            free(uicc_cap_tlv);
        }

        // ts102241Version (tag 0x86): 9.2.0
        uint8_t ts_ver[] = {0x09, 0x02, 0x00};
        uint8_t *ts_ver_tlv = NULL;
        uint32_t ts_ver_tlv_len = 0;
        build_tlv(&ts_ver_tlv, &ts_ver_tlv_len, 0x86, ts_ver, sizeof(ts_ver));
        if (ts_ver_tlv) {
            memcpy(info_ptr, ts_ver_tlv, ts_ver_tlv_len);
            info_ptr += ts_ver_tlv_len;
            info_total_len += ts_ver_tlv_len;
            free(ts_ver_tlv);
        }

        // globalplatformVersion (tag 0x87): 2.3.0
        uint8_t gp_ver[] = {0x02, 0x03, 0x00};
        uint8_t *gp_ver_tlv = NULL;
        uint32_t gp_ver_tlv_len = 0;
        build_tlv(&gp_ver_tlv, &gp_ver_tlv_len, 0x87, gp_ver, sizeof(gp_ver));
        if (gp_ver_tlv) {
            memcpy(info_ptr, gp_ver_tlv, gp_ver_tlv_len);
            info_ptr += gp_ver_tlv_len;
            info_total_len += gp_ver_tlv_len;
            free(gp_ver_tlv);
        }

        // rspCapability (tag 0x88): BIT STRING - simplified to avoid parsing issues
        uint8_t rsp_cap[] = {0x00};  // Just unused bits byte = 0
        uint8_t *rsp_cap_tlv = NULL;
        uint32_t rsp_cap_tlv_len = 0;
        build_tlv(&rsp_cap_tlv, &rsp_cap_tlv_len, 0x88, rsp_cap, sizeof(rsp_cap));
        if (rsp_cap_tlv) {
            memcpy(info_ptr, rsp_cap_tlv, rsp_cap_tlv_len);
            info_ptr += rsp_cap_tlv_len;
            info_total_len += rsp_cap_tlv_len;
            free(rsp_cap_tlv);
        }

        // euiccCiPKIdListForVerification (tag 0xA9)
        // PKID from generated CI certificate: 3C:45:E5:F0:09:D0:2C:75:EC:F3:D7:FB:0B:63:FD:31:7C:DE:2C:4E
        uint8_t ci_pk[] = {0x04, 0x14, 0x3C, 0x45, 0xE5, 0xF0, 0x09, 0xD0, 0x2C, 0x75,
                          0xEC, 0xF3, 0xD7, 0xFB, 0x0B, 0x63, 0xFD, 0x31, 0x7C, 0xDE, 0x2C, 0x4E};
        uint8_t *ci_pk_ver_tlv = NULL;
        uint32_t ci_pk_ver_tlv_len = 0;
        build_tlv(&ci_pk_ver_tlv, &ci_pk_ver_tlv_len, 0xA9, ci_pk, sizeof(ci_pk));
        if (ci_pk_ver_tlv) {
            memcpy(info_ptr, ci_pk_ver_tlv, ci_pk_ver_tlv_len);
            info_ptr += ci_pk_ver_tlv_len;
            info_total_len += ci_pk_ver_tlv_len;
            free(ci_pk_ver_tlv);
        }

        // euiccCiPKIdListForSigning (tag 0xAA)
        uint8_t *ci_pk_sign_tlv = NULL;
        uint32_t ci_pk_sign_tlv_len = 0;
        build_tlv(&ci_pk_sign_tlv, &ci_pk_sign_tlv_len, 0xAA, ci_pk, sizeof(ci_pk));
        if (ci_pk_sign_tlv) {
            memcpy(info_ptr, ci_pk_sign_tlv, ci_pk_sign_tlv_len);
            info_ptr += ci_pk_sign_tlv_len;
            info_total_len += ci_pk_sign_tlv_len;
            free(ci_pk_sign_tlv);
        }

        // forbiddenProfilePolicyRules (tag 0x99): pprUpdateControl, ppr1
        uint8_t ppr[] = {0x06, 0xC0};
        uint8_t *ppr_tlv = NULL;
        uint32_t ppr_tlv_len = 0;
        build_tlv(&ppr_tlv, &ppr_tlv_len, 0x99, ppr, sizeof(ppr));
        if (ppr_tlv) {
            memcpy(info_ptr, ppr_tlv, ppr_tlv_len);
            info_ptr += ppr_tlv_len;
            info_total_len += ppr_tlv_len;
            free(ppr_tlv);
        }

        // ppVersion: VersionType (no explicit tag, just the value)
        uint8_t pp_ver[] = {0x00, 0x00, 0x01};
        memcpy(info_ptr, pp_ver, sizeof(pp_ver));
        info_ptr += sizeof(pp_ver);
        info_total_len += sizeof(pp_ver);

        // sasAcreditationNumber: UTF8String (no explicit tag, just the value)
        const char *sas = "GI-BA-UP-0419";
        memcpy(info_ptr, (const uint8_t *)sas, strlen(sas));
        info_total_len += strlen(sas);

        // certificationDataObject (tag 0xAC)
        uint8_t cert_obj_buf[128];
        uint8_t *cert_obj_ptr = cert_obj_buf;
        uint32_t cert_obj_len = 0;

        const char *platform_label = "1.2.840.1234567/myPlatformLabel";
        uint8_t *pl_tlv = NULL;
        uint32_t pl_tlv_len = 0;
        build_tlv(&pl_tlv, &pl_tlv_len, 0x80, (const uint8_t *)platform_label, strlen(platform_label));
        if (pl_tlv) {
            memcpy(cert_obj_ptr, pl_tlv, pl_tlv_len);
            cert_obj_ptr += pl_tlv_len;
            cert_obj_len += pl_tlv_len;
            free(pl_tlv);
        }

        const char *discovery_url = "https://mycompany.com/myDLOARegistrar";
        uint8_t *du_tlv = NULL;
        uint32_t du_tlv_len = 0;
        build_tlv(&du_tlv, &du_tlv_len, 0x81, (const uint8_t *)discovery_url, strlen(discovery_url));
        if (du_tlv) {
            memcpy(cert_obj_ptr, du_tlv, du_tlv_len);
            cert_obj_len += du_tlv_len;
            free(du_tlv);
        }

        uint8_t *cert_obj_tlv = NULL;
        uint32_t cert_obj_tlv_len = 0;
        build_tlv(&cert_obj_tlv, &cert_obj_tlv_len, 0xAC, cert_obj_buf, cert_obj_len);
        if (cert_obj_tlv) {
            memcpy(info_ptr, cert_obj_tlv, cert_obj_tlv_len);
            info_total_len += cert_obj_tlv_len;
            free(cert_obj_tlv);
        }

        build_tlv(&resp_body, &resp_body_len, 0xBF22, info2_buf, info_total_len);
        break;
    }

    case 0xBF41: { // CancelSessionRequest
        fprintf(stderr, "[v-euicc] CancelSessionRequest received\n");
        
        // Parse to get transactionID and reason
        // For now, just build minimal response
        
        // Build euiccCancelSessionSigned (SEQUENCE tag 0x30)
        uint8_t cancel_signed_buf[128];
        uint8_t *cancel_ptr = cancel_signed_buf;
        uint32_t cancel_len = 0;
        
        // Add transactionID (tag 0x80)
        uint8_t *tid_tlv = NULL;
        uint32_t tid_tlv_len = 0;
        build_tlv(&tid_tlv, &tid_tlv_len, 0x80, state->transaction_id, state->transaction_id_len);
        if (tid_tlv) {
            memcpy(cancel_ptr, tid_tlv, tid_tlv_len);
            cancel_ptr += tid_tlv_len;
            cancel_len += tid_tlv_len;
            free(tid_tlv);
        }
        
        // Add smdpOid (context tag 0x81): OID 2.999.10 = 88 37 0A
        uint8_t smdp_oid[] = {0x81, 0x03, 0x88, 0x37, 0x0A}; // [1] IMPLICIT OBJECT IDENTIFIER
        memcpy(cancel_ptr, smdp_oid, sizeof(smdp_oid));
        cancel_ptr += sizeof(smdp_oid);
        cancel_len += sizeof(smdp_oid);
        
        // Add reason (context tag 0x82): endUserRejection = 0
        uint8_t reason[] = {0x82, 0x01, 0x00};
        memcpy(cancel_ptr, reason, sizeof(reason));
        cancel_len += sizeof(reason);
        
        // Wrap in SEQUENCE (tag 0x30)
        uint8_t *cancel_signed_tlv = NULL;
        uint32_t cancel_signed_tlv_len = 0;
        build_tlv(&cancel_signed_tlv, &cancel_signed_tlv_len, 0x30, cancel_signed_buf, cancel_len);
        if (!cancel_signed_tlv) {
            return -1;
        }
        
        // Sign euiccCancelSessionSigned
        uint8_t *cancel_signature = NULL;
        uint32_t cancel_signature_len = 0;
        
        if (state->euicc_private_key_len > 0 && state->euicc_private_key) {
            EVP_PKEY *pkey = (EVP_PKEY*)state->euicc_private_key;
            if (ecdsa_sign(cancel_signed_tlv, cancel_signed_tlv_len, pkey, &cancel_signature, &cancel_signature_len) < 0) {
                fprintf(stderr, "[v-euicc] CancelSession: signing failed\n");
                free(cancel_signed_tlv);
                return -1;
            }
        } else {
            free(cancel_signed_tlv);
            return -1;
        }
        
        // Build CancelSessionResponseOk: A0 { euiccCancelSessionSigned, euiccCancelSessionSignature }
        uint8_t cancel_resp_buf[256];
        uint8_t *cancel_resp_ptr = cancel_resp_buf;
        uint32_t cancel_resp_len = 0;
        
        memcpy(cancel_resp_ptr, cancel_signed_tlv, cancel_signed_tlv_len);
        cancel_resp_ptr += cancel_signed_tlv_len;
        cancel_resp_len += cancel_signed_tlv_len;
        free(cancel_signed_tlv);
        
        // Add signature (tag 0x5F37)
        uint8_t *cancel_sig_tlv = NULL;
        uint32_t cancel_sig_tlv_len = 0;
        build_tlv(&cancel_sig_tlv, &cancel_sig_tlv_len, 0x5F37, cancel_signature, cancel_signature_len);
        free(cancel_signature);
        
        if (cancel_sig_tlv) {
            memcpy(cancel_resp_ptr, cancel_sig_tlv, cancel_sig_tlv_len);
            cancel_resp_len += cancel_sig_tlv_len;
            free(cancel_sig_tlv);
        }
        
        // Wrap in CancelSessionResponseOk (tag 0xA0)
        uint8_t *cancel_ok_tlv = NULL;
        uint32_t cancel_ok_tlv_len = 0;
        build_tlv(&cancel_ok_tlv, &cancel_ok_tlv_len, 0xA0, cancel_resp_buf, cancel_resp_len);
        if (!cancel_ok_tlv) {
            return -1;
        }
        
        // Final response: BF41 { A0 { ... } }
        build_tlv(&resp_body, &resp_body_len, 0xBF41, cancel_ok_tlv, cancel_ok_tlv_len);
        free(cancel_ok_tlv);
        
        fprintf(stderr, "[v-euicc] CancelSession: Response generated with signature\n");
        break;
    }
    
    case 0xBF23: // InitialiseSecureChannelRequest (first BPP command)
    {
        // SGP.22 Section 3.1.3.3: Profile Installation
        // InitialiseSecureChannelRequest ::= BF23 {
        //     remoteOpId (80),
        //     transactionId [0] (A0 80),
        //     controlRefTemplate [6] (A6),
        //     smdpOtpk [APPLICATION 73] (5F49),
        //     smdpSign [APPLICATION 55] (5F37)
        // }
        fprintf(stderr, "[v-euicc] InitialiseSecureChannelRequest (BF23) received, len=%u\n", command_len);

        // Extract transactionId to verify it matches PrepareDownload
        // SGP.22 InitialiseSecureChannelRequest: BF23 { 82 <remoteOpId>, 80 <transactionId>, A6 <crt>, 5F49 <smdpOtpk>, 5F37 <smdpSign> }
        const uint8_t *ptr = command;
        uint32_t remaining = command_len;
        uint8_t transaction_id_found[16];
        uint8_t transaction_id_found_len = 0;
        
        // Skip BF23 tag and length to get to content
        if (remaining > 4 && ptr[0] == 0xBF && ptr[1] == 0x23) {
            ptr += 2;
            remaining -= 2;
            
            // Skip length field
            if (ptr[0] < 0x80) {
                ptr += 1;
                remaining -= 1;
            } else if (ptr[0] == 0x81) {
                ptr += 2;
                remaining -= 2;
            } else if (ptr[0] == 0x82) {
                ptr += 3;
                remaining -= 3;
            }
        }
        
        // Now parse content: Look for transactionId tag 0x80
        while (remaining > 2) {
            if (ptr[0] == 0x80) {
                uint8_t tid_len = ptr[1];
                if (tid_len <= 16 && remaining >= 2 + tid_len) {
                    memcpy(transaction_id_found, ptr + 2, tid_len);
                    transaction_id_found_len = tid_len;
                    fprintf(stderr, "[v-euicc] BF23: Found transactionID (%u bytes)\n", tid_len);
                    break;
                }
            }
            // Skip this TLV
            uint8_t skip_len = ptr[1];
            if (skip_len >= 0x80) break;  // Long form, stop
            ptr += 2 + skip_len;
            remaining -= 2 + skip_len;
        }
        
        // Verify transactionId matches the one from PrepareDownload
        if (transaction_id_found_len != state->transaction_id_len ||
            memcmp(transaction_id_found, state->transaction_id, transaction_id_found_len) != 0) {
            fprintf(stderr, "[v-euicc] BF23: TransactionID mismatch! Expected %u bytes, got %u bytes\n",
                    state->transaction_id_len, transaction_id_found_len);
            // Return error: Invalid Transaction ID (SGP.22 errorReason 0x03)
            return -1;
        }
        fprintf(stderr, "[v-euicc] BF23: TransactionID verified\n");

        // Extract smdpOtpk (SM-DP+ one-time public key, tag 0x5F49)
        // Reset ptr to beginning of BF23 content (after tag/length)
        ptr = command;
        remaining = command_len;
        uint8_t *smdp_otpk_data = NULL;
        uint32_t smdp_otpk_len = 0;
        
        // Skip BF23 tag and length again
        if (remaining > 4 && ptr[0] == 0xBF && ptr[1] == 0x23) {
            ptr += 2;
            remaining -= 2;
            
            // Skip length field
            if (ptr[0] < 0x80) {
                ptr += 1;
                remaining -= 1;
            } else if (ptr[0] == 0x81) {
                ptr += 2;
                remaining -= 2;
            } else if (ptr[0] == 0x82) {
                ptr += 3;
                remaining -= 3;
            }
        }
        
        // Look for smdpOtpk tag 0x5F49
        while (remaining > 3) {
            if (ptr[0] == 0x5F && ptr[1] == 0x49) {
                uint8_t len = ptr[2];
                if (len < 0x80 && remaining >= 3 + len) {
                    smdp_otpk_len = len;
                    smdp_otpk_data = malloc(smdp_otpk_len);
                    if (smdp_otpk_data) {
                        memcpy(smdp_otpk_data, ptr + 3, smdp_otpk_len);
                        fprintf(stderr, "[v-euicc] BF23: Extracted smdpOtpk (%u bytes)\n", smdp_otpk_len);
                    }
                    break;
                }
            }
            // Skip current TLV
            uint8_t skip_len = ptr[1];
            if (skip_len >= 0x80) {
                ptr++;
                remaining--;
            } else {
                ptr += 2 + skip_len;
                remaining -= 2 + skip_len;
            }
        }
        
        if (!smdp_otpk_data || smdp_otpk_len != 65) {
            fprintf(stderr, "[v-euicc] BF23: Failed to extract smdpOtpk or invalid length\n");
            free(smdp_otpk_data);
            return -1;
        }
        
        // Store SM-DP+ public key for later use
        free(state->smdp_otpk);
        state->smdp_otpk = smdp_otpk_data;
        state->smdp_otpk_len = smdp_otpk_len;
        
#ifdef ENABLE_PQC
        // Look for ML-KEM ciphertext (tag 0x5F4B) if in hybrid mode
        uint8_t *smdp_ct_kem = NULL;
        uint32_t smdp_ct_kem_len = 0;
        
        if (state->pqc_caps.hybrid_mode_active) {
            // Reset ptr to beginning to search for ciphertext
            ptr = command;
            remaining = command_len;
            
            fprintf(stderr, "[v-euicc] BF23: Looking for ML-KEM ciphertext (tag 0x5F4B) in %u bytes\n", remaining);
            
            // Skip BF23 tag and length
            if (remaining > 4 && ptr[0] == 0xBF && ptr[1] == 0x23) {
                ptr += 2;
                remaining -= 2;
                if (ptr[0] < 0x80) {
                    ptr += 1;
                    remaining -= 1;
                } else if (ptr[0] == 0x81) {
                    ptr += 2;
                    remaining -= 2;
                } else if (ptr[0] == 0x82) {
                    ptr += 3;
                    remaining -= 3;
                }
            }
            
            // Look for ciphertext tag 0x5F4B with proper bounds checking
            while (remaining > 3) {
                fprintf(stderr, "[v-euicc] BF23: Checking tag at offset, remaining=%u, tag=%02X%02X\n", 
                        remaining, ptr[0], ptr[1]);
                
                if (ptr[0] == 0x5F && ptr[1] == 0x4B) {
                    // Found ML-KEM ciphertext tag
                    fprintf(stderr, "[v-euicc] BF23: Found tag 0x5F4B\n");
                    
                    // Parse length (ptr[2])
                    uint32_t header_len = 3;  // tag (2 bytes) + length field start
                    if (ptr[2] < 0x80) {
                        // Short form
                        smdp_ct_kem_len = ptr[2];
                        fprintf(stderr, "[v-euicc] BF23: Short form length: %u\n", smdp_ct_kem_len);
                    } else if (ptr[2] == 0x82 && remaining >= 5) {
                        // Long form (2 bytes)
                        smdp_ct_kem_len = (ptr[3] << 8) | ptr[4];
                        header_len = 5;  // tag (2) + 0x82 (1) + length (2)
                        fprintf(stderr, "[v-euicc] BF23: Long form length: %u\n", smdp_ct_kem_len);
                    } else {
                        fprintf(stderr, "[v-euicc] BF23: Invalid length encoding: %02X\n", ptr[2]);
                        break;
                    }
                    
                    // Validate: ensure we have enough data
                    if (remaining < header_len + smdp_ct_kem_len) {
                        fprintf(stderr, "[v-euicc] BF23: Not enough data: have %u, need %u\n", 
                                remaining, header_len + smdp_ct_kem_len);
                        break;
                    }
                    
                    // Validate size
                    if (smdp_ct_kem_len > 0 && smdp_ct_kem_len <= 1088) {
                        smdp_ct_kem = malloc(smdp_ct_kem_len);
                        if (smdp_ct_kem) {
                            // Copy from correct offset (after header)
                            memcpy(smdp_ct_kem, ptr + header_len, smdp_ct_kem_len);
                            fprintf(stderr, "[v-euicc] BF23: Extracted ML-KEM ciphertext (%u bytes)\n", smdp_ct_kem_len);
                            
                            // Detailed PQC demo logging
                            fprintf(stderr, "[PQC-DEMO] InitialiseSecureChannel: ML-KEM ciphertext detected\n");
                            fprintf(stderr, "[PQC-DEMO]   Ciphertext Size: %u bytes (expected 1088)\n", smdp_ct_kem_len);
                            fprintf(stderr, "[PQC-DEMO]   Tag: 0x5F4B (ML-KEM ciphertext from SM-DP+)\n");
                            fprintf(stderr, "[PQC-DEMO]   First 32 bytes of CT: ");
                            for (int i = 0; i < 32 && i < smdp_ct_kem_len; i++) {
                                fprintf(stderr, "%02x", smdp_ct_kem[i]);
                            }
                            fprintf(stderr, "...\n");
                            fprintf(stderr, "[PQC-DEMO] Performing ML-KEM-768 decapsulation...\n");
                        } else {
                            fprintf(stderr, "[v-euicc] BF23: malloc failed for %u bytes\n", smdp_ct_kem_len);
                        }
                    } else {
                        fprintf(stderr, "[v-euicc] BF23: Invalid ciphertext length: %u\n", smdp_ct_kem_len);
                    }
                    break;
                }
                
                // Skip current TLV with proper bounds checking
                if (remaining < 2) break;
                
                uint32_t tag_len = ((ptr[0] & 0x1F) == 0x1F) ? 2 : 1;
                if (remaining < tag_len + 1) break;
                
                uint32_t value_len = 0;
                uint32_t len_field_size = 1;
                
                if (ptr[tag_len] < 0x80) {
                    value_len = ptr[tag_len];
                } else if (ptr[tag_len] == 0x81 && remaining >= tag_len + 2) {
                    value_len = ptr[tag_len + 1];
                    len_field_size = 2;
                } else if (ptr[tag_len] == 0x82 && remaining >= tag_len + 3) {
                    value_len = (ptr[tag_len + 1] << 8) | ptr[tag_len + 2];
                    len_field_size = 3;
                } else {
                    fprintf(stderr, "[v-euicc] BF23: Cannot parse length field\n");
                    break;
                }
                
                uint32_t total_tlv_len = tag_len + len_field_size + value_len;
                if (total_tlv_len > remaining) {
                    fprintf(stderr, "[v-euicc] BF23: TLV too large: %u > %u\n", total_tlv_len, remaining);
                    break;
                }
                
                fprintf(stderr, "[v-euicc] BF23: Skipping TLV (tag_len=%u, value_len=%u)\n", tag_len, value_len);
                ptr += total_tlv_len;
                remaining -= total_tlv_len;
            }
        }
#endif
        
        // Derive session keys using ECKA (SGP.22 Annex G) or hybrid mode
        if (!state->euicc_otsk || state->euicc_otsk_len != 32) {
            fprintf(stderr, "[v-euicc] BF23: eUICC ephemeral private key not available\n");
            return -1;
        }
        
#ifdef ENABLE_PQC
        if (state->pqc_caps.hybrid_mode_active && smdp_ct_kem && smdp_ct_kem_len > 0 && state->euicc_sk_kem) {
            fprintf(stderr, "[v-euicc] BF23: Using hybrid key agreement (ECDH + ML-KEM-768)\n");
            fprintf(stderr, "[v-euicc] BF23: CT length=%u, SK length=%u\n", smdp_ct_kem_len, state->euicc_sk_kem_len);
            
            // Step 1: Perform classical ECDH to get Z_ec
            uint8_t Z_ec[32];
            // We need to extract just the shared secret from ECDH
            // Reuse the ECDH computation from derive_session_keys_ecka
            EC_KEY *euicc_key = EC_KEY_new_by_curve_name(NID_X9_62_prime256v1);
            BIGNUM *priv_bn = BN_bin2bn(state->euicc_otsk, state->euicc_otsk_len, NULL);
            EC_KEY_set_private_key(euicc_key, priv_bn);
            BN_free(priv_bn);
            
            const EC_GROUP *group = EC_KEY_get0_group(euicc_key);
            EC_POINT *smdp_point = EC_POINT_new(group);
            BN_CTX *ctx = BN_CTX_new();
            EC_POINT_oct2point(group, smdp_point, state->smdp_otpk, state->smdp_otpk_len, ctx);
            
            EC_POINT *shared_point = EC_POINT_new(group);
            const BIGNUM *priv_key = EC_KEY_get0_private_key(euicc_key);
            EC_POINT_mul(group, shared_point, NULL, smdp_point, priv_key, ctx);
            
            BIGNUM *shared_x = BN_new();
            EC_POINT_get_affine_coordinates(group, shared_point, shared_x, NULL, ctx);
            memset(Z_ec, 0, 32);
            int shared_len = BN_num_bytes(shared_x);
            BN_bn2bin(shared_x, Z_ec + (32 - shared_len));
            
            BN_free(shared_x);
            EC_POINT_free(shared_point);
            BN_CTX_free(ctx);
            EC_POINT_free(smdp_point);
            EC_KEY_free(euicc_key);
            
            // Step 2: Perform ML-KEM decapsulation to get Z_kem
            uint8_t Z_kem[32];
            uint32_t z_kem_len = 32;
            
            if (mlkem_decapsulate(smdp_ct_kem, smdp_ct_kem_len,
                                 state->euicc_sk_kem, state->euicc_sk_kem_len,
                                 Z_kem, &z_kem_len) < 0) {
                fprintf(stderr, "[v-euicc] BF23: ML-KEM decapsulation failed\n");
                free(smdp_ct_kem);
                return -1;
            }
            
            free(smdp_ct_kem);
            
            // Step 3: Derive session keys using hybrid KDF
            if (derive_session_keys_hybrid(Z_ec, 32, Z_kem, 32,
                                          state->session_key_enc,
                                          state->session_key_mac) < 0) {
                fprintf(stderr, "[v-euicc] BF23: Hybrid session key derivation failed\n");
                memset(Z_ec, 0, 32);
                memset(Z_kem, 0, 32);
                return -1;
            }
            
            // Detailed PQC demo logging
            fprintf(stderr, "[PQC-DEMO] Hybrid KDF completed successfully\n");
            fprintf(stderr, "[PQC-DEMO]   ECDH shared secret: 32 bytes\n");
            fprintf(stderr, "[PQC-DEMO]   ML-KEM shared secret: 32 bytes\n");
            fprintf(stderr, "[PQC-DEMO]   Derived KEK: 16 bytes\n");
            fprintf(stderr, "[PQC-DEMO]   Derived KM: 16 bytes\n");
            fprintf(stderr, "[PQC-DEMO]   Security: Quantum-resistant (ML-KEM-768 + ECDH P-256)\n");
            
            // Securely erase shared secrets
            memset(Z_ec, 0, 32);
            memset(Z_kem, 0, 32);
            
            // Securely erase ML-KEM private key (no longer needed)
            memset(state->euicc_sk_kem, 0, state->euicc_sk_kem_len);
            free(state->euicc_sk_kem);
            state->euicc_sk_kem = NULL;
            state->euicc_sk_kem_len = 0;
            
            fprintf(stderr, "[v-euicc] BF23: Hybrid session keys derived successfully\n");
        } else {
#endif
            // Classical ECDH-only mode
            if (derive_session_keys_ecka(state->euicc_otsk, state->euicc_otsk_len,
                                         state->smdp_otpk, state->smdp_otpk_len,
                                         state->session_key_enc, state->session_key_mac) < 0) {
                fprintf(stderr, "[v-euicc] BF23: Session key derivation failed\n");
                return -1;
            }
            fprintf(stderr, "[v-euicc] BF23: Classical session keys derived\n");
#ifdef ENABLE_PQC
        }
#endif
        
        state->session_keys_derived = 1;
        state->bpp_commands_received++;
        fprintf(stderr, "[v-euicc] BF23: Secure channel established\n");

        // Build ProfileInstallationResult with success
        // SGP.22: Even intermediate BPP commands must return ProfileInstallationResult
        uint8_t pir_buf[256];
        uint8_t *pir_ptr = pir_buf;
        uint32_t pir_len = 0;
        
        // transactionId (tag 0x80)
        uint8_t *tid_tlv = NULL;
        uint32_t tid_tlv_len = 0;
        build_tlv(&tid_tlv, &tid_tlv_len, 0x80, state->transaction_id, state->transaction_id_len);
        if (tid_tlv) {
            memcpy(pir_ptr, tid_tlv, tid_tlv_len);
            pir_ptr += tid_tlv_len;
            pir_len += tid_tlv_len;
            free(tid_tlv);
        }
        
        // notificationMetadata BF2F { seqNumber (80) }
        uint8_t nm_buf[8];
        uint8_t seq_num = 0;  // Intermediate command
        uint8_t *seq_tlv = NULL;
        uint32_t seq_tlv_len = 0;
        build_tlv(&seq_tlv, &seq_tlv_len, 0x80, &seq_num, 1);
        uint8_t *nm_tlv = NULL;
        uint32_t nm_tlv_len = 0;
        if (seq_tlv) {
            build_tlv(&nm_tlv, &nm_tlv_len, 0xBF2F, seq_tlv, seq_tlv_len);
            free(seq_tlv);
        }
        if (nm_tlv) {
            memcpy(pir_ptr, nm_tlv, nm_tlv_len);
            pir_ptr += nm_tlv_len;
            pir_len += nm_tlv_len;
            free(nm_tlv);
        }
        
        // smdpOid (dummy OID for now)
        uint8_t dummy_oid[] = {0x06, 0x03, 0x04, 0x00, 0x7F};  // Dummy OID
        memcpy(pir_ptr, dummy_oid, sizeof(dummy_oid));
        pir_ptr += sizeof(dummy_oid);
        pir_len += sizeof(dummy_oid);
        
        // finalResult: successResult A2 { A0 {} }
        uint8_t success_result[] = {0xA2, 0x02, 0xA0, 0x00};  // A2 { A0 {} }
        memcpy(pir_ptr, success_result, sizeof(success_result));
        pir_len += sizeof(success_result);
        
        // Wrap in ProfileInstallationResultData (BF27)
        uint8_t *pir_data_tlv = NULL;
        uint32_t pir_data_tlv_len = 0;
        build_tlv(&pir_data_tlv, &pir_data_tlv_len, 0xBF27, pir_buf, pir_len);
        
        // Build ProfileInstallationResult (BF37) with dummy signature
        uint8_t pir_final_buf[512];
        uint8_t *pir_final_ptr = pir_final_buf;
        uint32_t pir_final_len = 0;
        
        if (pir_data_tlv) {
            memcpy(pir_final_ptr, pir_data_tlv, pir_data_tlv_len);
            pir_final_ptr += pir_data_tlv_len;
            pir_final_len += pir_data_tlv_len;
            free(pir_data_tlv);
        }
        
        // Add dummy euiccSignPIR (tag 0x5F37, 64 bytes)
        uint8_t dummy_sig[64] = {0};
        uint8_t *sig_tlv = NULL;
        uint32_t sig_tlv_len = 0;
        build_tlv(&sig_tlv, &sig_tlv_len, 0x5F37, dummy_sig, sizeof(dummy_sig));
        if (sig_tlv) {
            memcpy(pir_final_ptr, sig_tlv, sig_tlv_len);
            pir_final_len += sig_tlv_len;
            free(sig_tlv);
        }
        
        // Wrap in BF37 (ProfileInstallationResult)
        build_tlv(&resp_body, &resp_body_len, 0xBF37, pir_final_buf, pir_final_len);
        
        fprintf(stderr, "[v-euicc] BF23: Success, returning ProfileInstallationResult (%u bytes)\n", resp_body_len);
        
        // DEBUG: Dump first 40 bytes of response
        fprintf(stderr, "[v-euicc] BF23 Response hex: ");
        for (uint32_t i = 0; i < resp_body_len && i < 40; i++) {
            fprintf(stderr, "%02X ", resp_body[i]);
        }
        fprintf(stderr, "...\n");
        
        break;
    }

    case 0x86:   // Profile element data (sent individually by lpac)
    case 0x87:   // Encrypted APDU (ConfigureISDP or ReplaceSessionKeys)
    case 0x88:   // MAC-protected data (StoreMetadata)
    case 0xA0:   // firstSequenceOf87 (ConfigureISDP) wrapper
    case 0xA1:   // sequenceOf88 (StoreMetadata) wrapper
    case 0xA2:   // secondSequenceOf87 (ReplaceSessionKeys) wrapper (optional)
    case 0xA3:   // sequenceOf86 (Profile data) wrapper
    {
        // Store encrypted profile data from BPP commands
        // lpac sends both wrappers (A0/A1/A2/A3) and unwrapped inner commands (0x86/0x87/0x88)
        state->bpp_commands_received++;
        fprintf(stderr, "[v-euicc] BPP data command %04X received (count: %d), data_len: %u\n",
                tag, state->bpp_commands_received, command_len);

        // The command data is the BPP TLV data (after tag)
        // For A0-A3, format is: A0 LEN [encrypted_data]
        if (command_len >= 3) {  // tag(1) + len(1) + data
            uint8_t data_len = command[1];  // Length byte
            if (command_len >= 2 + data_len) {
                uint8_t *data = command + 2;  // Skip tag and length

                fprintf(stderr, "[v-euicc] BPP data: len=%u\n", data_len);

                // Ensure we have enough capacity in the buffer
                uint32_t required_capacity = state->bound_profile_package_len + data_len;
                if (required_capacity > state->bound_profile_package_capacity) {
                    uint32_t new_capacity = required_capacity * 2; // Double the capacity
                    uint8_t *new_buffer = realloc(state->bound_profile_package, new_capacity);
                    if (!new_buffer) {
                        fprintf(stderr, "[v-euicc] Failed to allocate BPP buffer\n");
                        return -1;
                    }
                    state->bound_profile_package = new_buffer;
                    state->bound_profile_package_capacity = new_capacity;
                }

                // Append the data
                memcpy(state->bound_profile_package + state->bound_profile_package_len, data, data_len);
                state->bound_profile_package_len += data_len;

                fprintf(stderr, "[v-euicc] Stored %u bytes of BPP data, total: %u bytes\n",
                        data_len, state->bound_profile_package_len);
            }
        }

        // For all but the last command (A3), return ProfileInstallationResult
        if (tag != 0xA3) {
            // Build ProfileInstallationResult with success for intermediate commands
            uint8_t pir_buf[256];
            uint8_t *pir_ptr = pir_buf;
            uint32_t pir_len = 0;
            
            // transactionId
            uint8_t *tid_tlv = NULL;
            uint32_t tid_tlv_len = 0;
            build_tlv(&tid_tlv, &tid_tlv_len, 0x80, state->transaction_id, state->transaction_id_len);
            if (tid_tlv) {
                memcpy(pir_ptr, tid_tlv, tid_tlv_len);
                pir_ptr += tid_tlv_len;
                pir_len += tid_tlv_len;
                free(tid_tlv);
            }
            
            // notificationMetadata BF2F { seqNumber }
            uint8_t seq_num = 0;
            uint8_t *seq_tlv = NULL;
            uint32_t seq_tlv_len = 0;
            build_tlv(&seq_tlv, &seq_tlv_len, 0x80, &seq_num, 1);
            uint8_t *nm_tlv = NULL;
            uint32_t nm_tlv_len = 0;
            if (seq_tlv) {
                build_tlv(&nm_tlv, &nm_tlv_len, 0xBF2F, seq_tlv, seq_tlv_len);
                free(seq_tlv);
            }
            if (nm_tlv) {
                memcpy(pir_ptr, nm_tlv, nm_tlv_len);
                pir_ptr += nm_tlv_len;
                pir_len += nm_tlv_len;
                free(nm_tlv);
            }
            
            // smdpOid
            uint8_t dummy_oid[] = {0x06, 0x03, 0x04, 0x00, 0x7F};
            memcpy(pir_ptr, dummy_oid, sizeof(dummy_oid));
            pir_ptr += sizeof(dummy_oid);
            pir_len += sizeof(dummy_oid);
            
            // finalResult: successResult A2 { A0 {} }
            uint8_t success_result[] = {0xA2, 0x02, 0xA0, 0x00};
            memcpy(pir_ptr, success_result, sizeof(success_result));
            pir_len += sizeof(success_result);
            
            // Wrap in ProfileInstallationResultData (BF27)
            uint8_t *pir_data_tlv = NULL;
            uint32_t pir_data_tlv_len = 0;
            build_tlv(&pir_data_tlv, &pir_data_tlv_len, 0xBF27, pir_buf, pir_len);
            
            // Build ProfileInstallationResult (BF37)
            uint8_t pir_final_buf[512];
            uint8_t *pir_final_ptr = pir_final_buf;
            uint32_t pir_final_len = 0;
            
            if (pir_data_tlv) {
                memcpy(pir_final_ptr, pir_data_tlv, pir_data_tlv_len);
                pir_final_ptr += pir_data_tlv_len;
                pir_final_len += pir_data_tlv_len;
                free(pir_data_tlv);
            }
            
            // Add dummy signature
            uint8_t dummy_sig[64] = {0};
            uint8_t *sig_tlv = NULL;
            uint32_t sig_tlv_len = 0;
            build_tlv(&sig_tlv, &sig_tlv_len, 0x5F37, dummy_sig, sizeof(dummy_sig));
            if (sig_tlv) {
                memcpy(pir_final_ptr, sig_tlv, sig_tlv_len);
                pir_final_len += sig_tlv_len;
                free(sig_tlv);
            }
            
            // Wrap in BF37
            build_tlv(&resp_body, &resp_body_len, 0xBF37, pir_final_buf, pir_final_len);
            
            fprintf(stderr, "[v-euicc] BPP command %04X: Returning ProfileInstallationResult\n", tag);
            break;
        }
        
        // Last command (sequenceOf86) - install the profile and return ProfileInstallationResult
        fprintf(stderr, "[v-euicc] Final BPP command, installing profile from %u bytes of BPP data\n",
                state->bound_profile_package_len);

        // Install the profile (Phase A: just store the data, no decryption)
        if (state->bound_profile_package_len > 0) {
            // Ensure we have enough capacity in installed profiles buffer
            uint32_t required_capacity = state->installed_profiles_len + state->bound_profile_package_len;
            if (required_capacity > state->installed_profiles_capacity) {
                uint32_t new_capacity = required_capacity * 2;
                uint8_t *new_buffer = realloc(state->installed_profiles, new_capacity);
                if (!new_buffer) {
                    fprintf(stderr, "[v-euicc] Failed to allocate installed profiles buffer\n");
                    return -1;
                }
                state->installed_profiles = new_buffer;
                state->installed_profiles_capacity = new_capacity;
            }

            // "Install" the profile by copying the data
            memcpy(state->installed_profiles + state->installed_profiles_len,
                   state->bound_profile_package, state->bound_profile_package_len);
            state->installed_profiles_len += state->bound_profile_package_len;

            fprintf(stderr, "[v-euicc] Stored %u bytes of BPP data\n",
                    state->bound_profile_package_len);

            // Create profile metadata entry
            struct profile_metadata *new_profile = malloc(sizeof(struct profile_metadata));
            if (new_profile) {
                memset(new_profile, 0, sizeof(struct profile_metadata));
                
                // Generate ICCID (for now, use a test ICCID based on matching_id)
                // In a real implementation, this would be extracted from decrypted profile
                snprintf(new_profile->iccid, sizeof(new_profile->iccid), "8949449999999990049");
                
                // Generate ISD-P AID (dummy for now)
                snprintf(new_profile->isdp_aid, sizeof(new_profile->isdp_aid), 
                        "A0000005591010FFFFFFFF8900001000");
                
                // Set profile state (disabled by default)
                new_profile->state = PROFILE_STATE_DISABLED;
                
                // Use matching_id as profile name
                if (strlen(state->matching_id) > 0) {
                    strncpy(new_profile->profile_name, state->matching_id, 
                           sizeof(new_profile->profile_name) - 1);
                } else {
                    strncpy(new_profile->profile_name, "Unknown Profile", 
                           sizeof(new_profile->profile_name) - 1);
                }
                
                // Set service provider name (for demo)
                strncpy(new_profile->service_provider_name, "OsmocomSPN", 
                       sizeof(new_profile->service_provider_name) - 1);
                
                // Store profile data
                new_profile->profile_data = malloc(state->bound_profile_package_len);
                if (new_profile->profile_data) {
                    memcpy(new_profile->profile_data, state->bound_profile_package, 
                          state->bound_profile_package_len);
                    new_profile->profile_data_len = state->bound_profile_package_len;
                }
                
                // Add to linked list
                new_profile->next = state->profiles;
                state->profiles = new_profile;
                
                fprintf(stderr, "[v-euicc] Created profile metadata: ICCID=%s, Name=%s\n",
                       new_profile->iccid, new_profile->profile_name);
            }

            // Clear the BPP buffer after installation
            free(state->bound_profile_package);
            state->bound_profile_package = NULL;
            state->bound_profile_package_len = 0;
            state->bound_profile_package_capacity = 0;
        } else {
            fprintf(stderr, "[v-euicc] No BPP data to install\n");
        }
        
        // TEMP: Skip ProfileInstallationResult building
        
        // Build ProfileInstallationResultData
        uint8_t pir_data_buf[256];
        uint8_t *pir_ptr = pir_data_buf;
        uint32_t pir_len = 0;
        
        // Add transactionID (tag 0x80)
        uint8_t *tid_tlv = NULL;
        uint32_t tid_tlv_len = 0;
        build_tlv(&tid_tlv, &tid_tlv_len, 0x80, state->transaction_id, state->transaction_id_len);
        if (tid_tlv) {
            memcpy(pir_ptr, tid_tlv, tid_tlv_len);
            pir_ptr += tid_tlv_len;
            pir_len += tid_tlv_len;
            free(tid_tlv);
        }
        
        // Add notificationMetadata (tag 0xBF2F)
        uint8_t notif_buf[64];
        uint8_t *notif_ptr = notif_buf;
        uint32_t notif_len = 0;
        
        // seqNumber (tag 0x80)
        uint8_t seq_num_buf[4];
        uint32_t seq_num_len = sizeof(seq_num_buf);
        seq_num_buf[0] = (state->notification_seq_number >> 24) & 0xFF;
        seq_num_buf[1] = (state->notification_seq_number >> 16) & 0xFF;
        seq_num_buf[2] = (state->notification_seq_number >> 8) & 0xFF;
        seq_num_buf[3] = state->notification_seq_number & 0xFF;
        
        fprintf(stderr, "[v-euicc] Building notificationMetadata: seqNumber=%u, buf=[%02X %02X %02X %02X]\n",
                state->notification_seq_number, seq_num_buf[0], seq_num_buf[1], seq_num_buf[2], seq_num_buf[3]);
        
        // Find actual length (trim leading zeros)
        while (seq_num_len > 1 && seq_num_buf[sizeof(seq_num_buf) - seq_num_len] == 0) {
            seq_num_len--;
        }
        
        fprintf(stderr, "[v-euicc] After trimming: seq_num_len=%u, data starts at offset %u\n",
                seq_num_len, (uint32_t)(sizeof(seq_num_buf) - seq_num_len));
        
        uint8_t *seq_tlv = NULL;
        uint32_t seq_tlv_len = 0;
        build_tlv(&seq_tlv, &seq_tlv_len, 0x80, seq_num_buf + (sizeof(seq_num_buf) - seq_num_len), seq_num_len);
        if (seq_tlv) {
            memcpy(notif_ptr, seq_tlv, seq_tlv_len);
            notif_ptr += seq_tlv_len;
            notif_len += seq_tlv_len;
            free(seq_tlv);
        }
        
        // profileManagementOperation (tag 0x81): install = 0x80
        uint8_t pm_op[] = {0x81, 0x02, 0x01, 0x80};  // BIT STRING with install bit set
        memcpy(notif_ptr, pm_op, sizeof(pm_op));
        notif_ptr += sizeof(pm_op);
        notif_len += sizeof(pm_op);
        
        // notificationAddress (tag 0x0C): use localhost
        const char *notif_addr = "localhost";
        uint8_t *addr_tlv = NULL;
        uint32_t addr_tlv_len = 0;
        build_tlv(&addr_tlv, &addr_tlv_len, 0x0C, (const uint8_t*)notif_addr, strlen(notif_addr));
        if (addr_tlv) {
            memcpy(notif_ptr, addr_tlv, addr_tlv_len);
            notif_len += addr_tlv_len;
            free(addr_tlv);
        }
        
        // Wrap notificationMetadata
        uint8_t *notif_tlv = NULL;
        uint32_t notif_tlv_len = 0;
        build_tlv(&notif_tlv, &notif_tlv_len, 0xBF2F, notif_buf, notif_len);
        if (notif_tlv) {
            memcpy(pir_ptr, notif_tlv, notif_tlv_len);
            pir_ptr += notif_tlv_len;
            pir_len += notif_tlv_len;
            free(notif_tlv);
        }
        
        // Add smdpOid: OID 2.999.10
        uint8_t smdp_oid[] = {0x06, 0x03, 0x88, 0x37, 0x0A}; // OBJECT IDENTIFIER
        memcpy(pir_ptr, smdp_oid, sizeof(smdp_oid));
        pir_ptr += sizeof(smdp_oid);
        pir_len += sizeof(smdp_oid);
        
        // Add finalResult (tag 0xA2) - SUCCESS
        // SGP.22: finalResult [2] CHOICE { successResult [0], errorResult [1] }
        // For success: A2 { A0 { SEQUENCE { aid, simaResponse } } }
        uint8_t success_result_buf[64];
        uint8_t *success_ptr = success_result_buf;
        uint32_t success_len = 0;
        
        // Build SEQUENCE { aid (4F), simaResponse (04) }
        uint8_t dummy_aid[] = {0x4F, 0x10, 0xA0, 0x00, 0x00, 0x05, 0x59, 0x10, 0x10, 0xFF, 0xFF, 0xFF, 0xFF, 0x89, 0x00, 0x00, 0x10, 0x00};
        memcpy(success_ptr, dummy_aid, sizeof(dummy_aid));
        success_ptr += sizeof(dummy_aid);
        success_len += sizeof(dummy_aid);
        
        // simaResponse (tag 0x04): 9000 (success)
        uint8_t sima[] = {0x04, 0x02, 0x90, 0x00};
        memcpy(success_ptr, sima, sizeof(sima));
        success_len += sizeof(sima);
        
        // Wrap in SEQUENCE (0x30)
        uint8_t *success_seq = NULL;
        uint32_t success_seq_len = 0;
        build_tlv(&success_seq, &success_seq_len, 0x30, success_result_buf, success_len);

        // Wrap in successResult [0] (0xA0)
        uint8_t *success_result_tlv = NULL;
        uint32_t success_result_tlv_len = 0;
        build_tlv(&success_result_tlv, &success_result_tlv_len, 0xA0, success_seq, success_seq_len);
        free(success_seq);

        // Wrap in finalResult [2] (0xA2)
        uint8_t *final_result_tlv = NULL;
        uint32_t final_result_tlv_len = 0;
        build_tlv(&final_result_tlv, &final_result_tlv_len, 0xA2, success_result_tlv, success_result_tlv_len);
        free(success_result_tlv);
        
        if (final_result_tlv) {
            memcpy(pir_ptr, final_result_tlv, final_result_tlv_len);
            pir_ptr += final_result_tlv_len;
            pir_len += final_result_tlv_len;
            free(final_result_tlv);
        }
        
        // Wrap ProfileInstallationResultData (tag 0xBF27)
        uint8_t *pir_data_tlv = NULL;
        uint32_t pir_data_tlv_len = 0;
        build_tlv(&pir_data_tlv, &pir_data_tlv_len, 0xBF27, pir_data_buf, pir_len);
        if (!pir_data_tlv) {
            return -1;
        }
        
        // Sign the ProfileInstallationResultData
        uint8_t *pir_signature = NULL;
        uint32_t pir_signature_len = 0;
        
        if (state->euicc_private_key_len > 0 && state->euicc_private_key) {
            EVP_PKEY *pkey = (EVP_PKEY*)state->euicc_private_key;
            if (ecdsa_sign(pir_data_tlv, pir_data_tlv_len, pkey, &pir_signature, &pir_signature_len) < 0) {
                fprintf(stderr, "[v-euicc] ProfileInstallationResult: signing failed\n");
                free(pir_data_tlv);
                return -1;
            }
        } else {
            free(pir_data_tlv);
            return -1;
        }
        
        // Build final ProfileInstallationResult response
        uint8_t pir_resp_buf[2048];
        uint8_t *pir_resp_ptr = pir_resp_buf;
        uint32_t pir_resp_len = 0;
        
        // Add ProfileInstallationResultData
        memcpy(pir_resp_ptr, pir_data_tlv, pir_data_tlv_len);
        pir_resp_ptr += pir_data_tlv_len;
        pir_resp_len += pir_data_tlv_len;
        free(pir_data_tlv);
        
        // Add signature (tag 0x5F37)
        uint8_t *pir_sig_tlv = NULL;
        uint32_t pir_sig_tlv_len = 0;
        build_tlv(&pir_sig_tlv, &pir_sig_tlv_len, 0x5F37, pir_signature, pir_signature_len);
        free(pir_signature);
        
        if (pir_sig_tlv) {
            memcpy(pir_resp_ptr, pir_sig_tlv, pir_sig_tlv_len);
            pir_resp_len += pir_sig_tlv_len;
            free(pir_sig_tlv);
        }
        
        // Wrap in ProfileInstallationResult (tag 0xBF37)
        build_tlv(&resp_body, &resp_body_len, 0xBF37, pir_resp_buf, pir_resp_len);
        
        fprintf(stderr, "[v-euicc] ProfileInstallationResult built successfully (%u bytes)\n", resp_body_len);
        
        // DEBUG: Dump first 60 bytes of final response
        fprintf(stderr, "[v-euicc] Final A3 Response hex: ");
        for (uint32_t i = 0; i < resp_body_len && i < 60; i++) {
            fprintf(stderr, "%02X ", resp_body[i]);
        }
        fprintf(stderr, "...\n");
        
        break;
    }

    case 0xBF2D: // GetProfilesInfo (ES10c)
    {
        fprintf(stderr, "[v-euicc] GetProfilesInfo (BF2D) received - building profile list\n");
        
        // Build ProfileInfoListResponse: BF2D { A0 { E3 {...}, E3 {...}, ... } }
        uint8_t profile_list_buf[8192];
        uint8_t *list_ptr = profile_list_buf;
        uint32_t list_len = 0;
        
        // Iterate through all profiles
        struct profile_metadata *profile = state->profiles;
        int profile_count = 0;
        
        while (profile) {
            uint8_t profile_info_buf[512];
            uint8_t *info_ptr = profile_info_buf;
            uint32_t info_len = 0;
            
            // Add ICCID (tag 0x5A) - must be BCD encoded
            uint8_t iccid_bcd[10];
            uint32_t iccid_len = strlen(profile->iccid);
            // Convert string ICCID to BCD
            for (uint32_t i = 0; i < 10; i++) {
                uint8_t high = (i*2 < iccid_len) ? (profile->iccid[i*2] - '0') : 0xF;
                uint8_t low = (i*2+1 < iccid_len) ? (profile->iccid[i*2+1] - '0') : 0xF;
                iccid_bcd[i] = (high << 4) | low;
            }
            
            uint8_t *iccid_tlv = NULL;
            uint32_t iccid_tlv_len = 0;
            build_tlv(&iccid_tlv, &iccid_tlv_len, 0x5A, iccid_bcd, 10);
            if (iccid_tlv) {
                memcpy(info_ptr, iccid_tlv, iccid_tlv_len);
                info_ptr += iccid_tlv_len;
                info_len += iccid_tlv_len;
                free(iccid_tlv);
            }
            
            // Add ISD-P AID (tag 0x4F) - hex string to binary
            if (strlen(profile->isdp_aid) > 0) {
                uint8_t aid_bin[16];
                uint32_t aid_bin_len = euicc_hexutil_hex2bin(aid_bin, sizeof(aid_bin), profile->isdp_aid);
                
                uint8_t *aid_tlv = NULL;
                uint32_t aid_tlv_len = 0;
                build_tlv(&aid_tlv, &aid_tlv_len, 0x4F, aid_bin, aid_bin_len);
                if (aid_tlv) {
                    memcpy(info_ptr, aid_tlv, aid_tlv_len);
                    info_ptr += aid_tlv_len;
                    info_len += aid_tlv_len;
                    free(aid_tlv);
                }
            }
            
            // Add profileState (tag 0x9F70)
            uint8_t state_val = (uint8_t)profile->state;
            uint8_t *state_tlv = NULL;
            uint32_t state_tlv_len = 0;
            build_tlv(&state_tlv, &state_tlv_len, 0x9F70, &state_val, 1);
            if (state_tlv) {
                memcpy(info_ptr, state_tlv, state_tlv_len);
                info_ptr += state_tlv_len;
                info_len += state_tlv_len;
                free(state_tlv);
            }
            
            // Add serviceProviderName (tag 0x91)
            if (strlen(profile->service_provider_name) > 0) {
                uint8_t *spn_tlv = NULL;
                uint32_t spn_tlv_len = 0;
                build_tlv(&spn_tlv, &spn_tlv_len, 0x91, 
                         (const uint8_t*)profile->service_provider_name, 
                         strlen(profile->service_provider_name));
                if (spn_tlv) {
                    memcpy(info_ptr, spn_tlv, spn_tlv_len);
                    info_ptr += spn_tlv_len;
                    info_len += spn_tlv_len;
                    free(spn_tlv);
                }
            }
            
            // Add profileName (tag 0x92)
            if (strlen(profile->profile_name) > 0) {
                uint8_t *name_tlv = NULL;
                uint32_t name_tlv_len = 0;
                build_tlv(&name_tlv, &name_tlv_len, 0x92, 
                         (const uint8_t*)profile->profile_name, 
                         strlen(profile->profile_name));
                if (name_tlv) {
                    memcpy(info_ptr, name_tlv, name_tlv_len);
                    info_ptr += name_tlv_len;
                    info_len += name_tlv_len;
                    free(name_tlv);
                }
            }
            
            // Wrap in ProfileInfo (tag 0xE3)
            uint8_t *profile_info_tlv = NULL;
            uint32_t profile_info_tlv_len = 0;
            build_tlv(&profile_info_tlv, &profile_info_tlv_len, 0xE3, profile_info_buf, info_len);
            if (profile_info_tlv) {
                memcpy(list_ptr, profile_info_tlv, profile_info_tlv_len);
                list_ptr += profile_info_tlv_len;
                list_len += profile_info_tlv_len;
                free(profile_info_tlv);
            }
            
            profile = profile->next;
            profile_count++;
        }
        
        fprintf(stderr, "[v-euicc] Built profile list with %d profiles, total len: %u\n", 
                profile_count, list_len);
        
        // Wrap in profileInfoListOk (tag 0xA0)
        uint8_t *list_ok_tlv = NULL;
        uint32_t list_ok_tlv_len = 0;
        build_tlv(&list_ok_tlv, &list_ok_tlv_len, 0xA0, profile_list_buf, list_len);
        if (!list_ok_tlv) {
            return -1;
        }
        
        // Wrap in GetProfilesInfoResponse (tag 0xBF2D)
        build_tlv(&resp_body, &resp_body_len, 0xBF2D, list_ok_tlv, list_ok_tlv_len);
        free(list_ok_tlv);
        
        fprintf(stderr, "[v-euicc] GetProfilesInfo response built, total len: %u\n", resp_body_len);
        break;
    }

    default:
        fprintf(stderr, "Unsupported ES10x command: %04X (len=%u)\n", tag, command_len);
        fprintf(stderr, "First 16 bytes: ");
        for (uint32_t i = 0; i < (command_len < 16 ? command_len : 16); i++) {
            fprintf(stderr, "%02X ", command[i]);
        }
        fprintf(stderr, "\n");
        
        // Return error response with status 6D00 (INS not supported)
        *response_len = 2;
        *response = malloc(*response_len);
        if (*response) {
            (*response)[0] = 0x6D;
            (*response)[1] = 0x00;
            return 0;  // Return success with error status in response
        }
        return -1;
    }

    if (!resp_body) {
        return -1;
    }

    // Append status bytes
    *response_len = resp_body_len + 2;
    *response = malloc(*response_len);
    if (!*response) {
        free(resp_body);
        return -1;
    }

    memcpy(*response, resp_body, resp_body_len);
    memcpy(*response + resp_body_len, status, 2);

    free(resp_body);
    return 0;
}

int apdu_handle_transmit(struct euicc_state *state, uint8_t **response, uint32_t *response_len,
                        const uint8_t *command, uint32_t command_len) {
    if (state->logic_channel < 0) {
        fprintf(stderr, "No logic channel open\n");
        return -1;
    }

    // For ES10x commands, the command is wrapped in APDU envelope
    // We expect CLA INS P1 P2 LC DATA format
    if (command_len < 5) {
        fprintf(stderr, "[v-euicc] APDU too short: %u bytes\n", command_len);
        return -1;
    }

    uint8_t cla = command[0];
    uint8_t ins = command[1];
    uint8_t p1 = command[2];
    uint8_t p2 = command[3];
    uint8_t lc = command[4];

    fprintf(stderr, "[v-euicc] APDU: CLA=%02X INS=%02X P1=%02X P2=%02X LC=%02X ", cla, ins, p1, p2, lc);
    if (lc > 0 && lc <= 16) {
        fprintf(stderr, "DATA: ");
        for (uint32_t i = 0; i < lc && i < 16; i++) {
            fprintf(stderr, "%02X ", command[i]);
        }
    }
    fprintf(stderr, "\n");

    // Check for GET RESPONSE command (INS=0xC0)
    if (ins == 0xC0) {
        fprintf(stderr, "[v-euicc] GET RESPONSE command - returning empty response\n");
        *response_len = 2;
        *response = malloc(*response_len);
        if (*response) {
            (*response)[0] = 0x6D;  // INS not supported  
            (*response)[1] = 0x00;
        }
        return 0;
    }

    // Verify it's an ES10x command (INS=0xE2)
    if (ins != 0xE2) {
        fprintf(stderr, "[v-euicc] Unsupported INS: %02X\n", ins);
        *response_len = 2;
        *response = malloc(*response_len);
        if (*response) {
            (*response)[0] = 0x6D;  // INS not supported
            (*response)[1] = 0x00;
        }
        return 0;
    }

    // Extract ES10x command data
    const uint8_t *es10x_data = command + 5;
    uint32_t es10x_data_len = command_len - 5;

    // Handle command segmentation (SGP.22 Section 2.6.3)
    // P1: bit 7 set (0x80) = last segment, clear = more segments
    // P2: segment sequence number
    bool is_last_segment = (p1 & 0x80) != 0;
    uint8_t segment_number = p2;

    if (!is_last_segment) {
        // More segments to follow - buffer this segment
        fprintf(stderr, "[v-euicc] Buffering segment %u (%u bytes)\n", segment_number, es10x_data_len);
        
        // Ensure buffer has enough capacity
        // Increased headroom to 4096 bytes to handle ML-KEM-768 ciphertext (1088 bytes) + overhead
        uint32_t new_len = state->segment_buffer_len + es10x_data_len;
        if (new_len > state->segment_buffer_capacity) {
            uint32_t new_capacity = new_len + 4096;  // Increased for PQC support
            uint8_t *new_buffer = realloc(state->segment_buffer, new_capacity);
            if (!new_buffer) {
                fprintf(stderr, "[v-euicc] Failed to allocate segment buffer\n");
                return -1;
            }
            state->segment_buffer = new_buffer;
            state->segment_buffer_capacity = new_capacity;
        }
        
        // Append segment data
        memcpy(state->segment_buffer + state->segment_buffer_len, es10x_data, es10x_data_len);
        state->segment_buffer_len += es10x_data_len;
        
        // Return success acknowledgment (9000)
        *response_len = 2;
        *response = malloc(*response_len);
        if (*response) {
            (*response)[0] = 0x90;
            (*response)[1] = 0x00;
        }
        return 0;
    } else {
        // Last segment - process complete command
        uint8_t *complete_command;
        uint32_t complete_command_len;
        
        if (state->segment_buffer_len > 0) {
            // We have buffered segments - append this final one
            fprintf(stderr, "[v-euicc] Processing final segment %u (total buffered: %u + %u bytes)\n", 
                    segment_number, state->segment_buffer_len, es10x_data_len);
            
            complete_command_len = state->segment_buffer_len + es10x_data_len;
            complete_command = malloc(complete_command_len);
            if (!complete_command) {
                return -1;
            }
            
            memcpy(complete_command, state->segment_buffer, state->segment_buffer_len);
            memcpy(complete_command + state->segment_buffer_len, es10x_data, es10x_data_len);
            
            // Clear segment buffer
            free(state->segment_buffer);
            state->segment_buffer = NULL;
            state->segment_buffer_len = 0;
            state->segment_buffer_capacity = 0;
        } else {
            // Single segment command
            fprintf(stderr, "[v-euicc] Processing single-segment command (%u bytes)\n", es10x_data_len);
            complete_command = (uint8_t *)es10x_data;  // Cast away const for processing
            complete_command_len = es10x_data_len;
        }
        
        int result = process_es10x_command(state, response, response_len, complete_command, complete_command_len);
        
        // Free allocated buffer if we combined segments
        if (complete_command != es10x_data) {
            free(complete_command);
        }
        
        return result;
    }
}

