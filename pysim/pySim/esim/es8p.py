"""Implementation of GSMA eSIM RSP (Remote SIM Provisioning) ES8+ as per SGP22 v3.0 Section 5.5"""

# (C) 2023-2024 by Harald Welte <laforge@osmocom.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import Dict, List, Optional
from cryptography.hazmat.primitives.asymmetric import ec
from osmocom.utils import b2h, h2b
from osmocom.tlv import bertlv_encode_tag, bertlv_encode_len, bertlv_parse_one_rawtag
from osmocom.tlv import bertlv_return_one_rawtlv

import pySim.esim.rsp as rsp
from pySim.esim.bsp import BspInstance
from pySim.esim import PMO

import logging
logger = logging.getLogger(__name__)

# Given that GSMA RSP uses ASN.1 in a very weird way, we actually cannot encode the full data type before
# signing, but we have to build parts of it separately first, then sign that, so we can put the signature
# into the same sequence as the signed data.  We use the existing pySim TLV code for this.

def wrap_as_der_tlv(tag: int, val: bytes) -> bytes:
    """Wrap the 'value' into a DER-encoded TLV."""
    return bertlv_encode_tag(tag) + bertlv_encode_len(len(val)) + val

def gen_init_sec_chan_signed_part(iscsp: Dict) -> bytes:
    """Generate the concatenated remoteOpId, transactionId, controlRefTemplate and smdpOtpk data objects
    without the outer SEQUENCE tag / length or the remainder of initialiseSecureChannel, as is required
    for signing purpose."""
    out = b''
    out += wrap_as_der_tlv(0x82, bytes([iscsp['remoteOpId']]))
    out += wrap_as_der_tlv(0x80, iscsp['transactionId'])

    crt = iscsp['controlRefTemplate']
    out_crt = wrap_as_der_tlv(0x80, crt['keyType'])
    out_crt += wrap_as_der_tlv(0x81, crt['keyLen'])
    out_crt += wrap_as_der_tlv(0x84, crt['hostId'])
    out += wrap_as_der_tlv(0xA6, out_crt)

    out += wrap_as_der_tlv(0x5F49, iscsp['smdpOtpk'])
    return out


# SGP.22 Section 5.5.1
def gen_initialiseSecureChannel(transactionId: str, host_id: bytes, smdp_otpk: bytes, euicc_otpk: bytes, dp_pb):
    """Generate decoded representation of (signed) initialiseSecureChannel (SGP.22 5.5.2)"""
    init_scr = { 'remoteOpId': 1, # installBoundProfilePackage
                 'transactionId': h2b(transactionId),
                 # GlobalPlatform Card Specification Amendment F [13] section 6.5.2.3 for the Mutual Authentication Data Field
                 'controlRefTemplate': { 'keyType': bytes([0x88]), 'keyLen': bytes([16]), 'hostId': host_id },
                 'smdpOtpk': smdp_otpk, # otPK.DP.KA
                }
    to_sign = gen_init_sec_chan_signed_part(init_scr) + wrap_as_der_tlv(0x5f49, euicc_otpk)
    init_scr['smdpSign'] = dp_pb.ecdsa_sign(to_sign)
    return init_scr

def gen_replace_session_keys(ppk_enc: bytes, ppk_cmac: bytes, initial_mcv: bytes) -> bytes:
    """Generate encoded (but unsigned) ReplaceSessionKeysReqest DO (SGP.22 5.5.4)"""
    rsk = { 'ppkEnc': ppk_enc, 'ppkCmac': ppk_cmac, 'initialMacChainingValue': initial_mcv }
    return rsp.asn1.encode('ReplaceSessionKeysRequest', rsk)


class ProfileMetadata:
    """Representation of Profile metadata. Right now only the mandatory bits are
    supported, but in general this should follow the StoreMetadataRequest of SGP.22 5.5.3"""
    def __init__(self, iccid_bin: bytes, spn: str, profile_name: str):
        self.iccid_bin = iccid_bin
        self.spn = spn
        self.profile_name = profile_name
        self.icon = None
        self.icon_type = None
        self.notifications = []

    def set_icon(self, is_png: bool, icon_data: bytes):
        """Set the icon that is part of the metadata."""
        if len(icon_data) > 1024:
            raise ValueError('Icon data must not exceed 1024 bytes')
        self.icon = icon_data
        if is_png:
            self.icon_type = 1
        else:
            self.icon_type = 0

    def add_notification(self, event: str, address: str):
        """Add an 'other' notification to the notification configuration of the metadata"""
        self.notifications.append((event, address))

    def gen_store_metadata_request(self) -> bytes:
        """Generate encoded (but unsigned) StoreMetadataRequest DO (SGP.22 5.5.3)"""
        smr = {
            'iccid': self.iccid_bin,
            'serviceProviderName': self.spn,
            'profileName': self.profile_name,
        }
        if self.icon:
            smr['icon'] = self.icon
            smr['iconType'] = self.icon_type
        nci = []
        for n in self.notifications:
            pmo = PMO(n[0])
            nci.append({'profileManagementOperation': pmo.to_bitstring(), 'notificationAddress': n[1]})
        if len(nci):
            smr['notificationConfigurationInfo'] = nci
        return rsp.asn1.encode('StoreMetadataRequest', smr)


class ProfilePackage:
    def __init__(self, metadata: Optional[ProfileMetadata] = None):
        self.metadata = metadata

class UnprotectedProfilePackage(ProfilePackage):
    """Representing an unprotected profile package (UPP) as defined in SGP.22 Section 2.5.2"""

    @classmethod
    def from_der(cls, der: bytes, metadata: Optional[ProfileMetadata] = None) -> 'UnprotectedProfilePackage':
        """Load an UPP from its DER representation."""
        inst = cls(metadata=metadata)
        cls.der = der
        # TODO: we later certainly want to parse it so we can perform modification (IMSI, key material, ...)
        # just like in the traditional SIM/USIM dynamic data phase at the end of personalization
        return inst

    def to_der(self):
        """Return the DER representation of the UPP."""
        # TODO: once we work on decoded structures, we may want to re-encode here
        return self.der

class ProtectedProfilePackage(ProfilePackage):
    """Representing a protected profile package (PPP) as defined in SGP.22 Section 2.5.3"""

    @classmethod
    def from_upp(cls, upp: UnprotectedProfilePackage, bsp: BspInstance) -> 'ProtectedProfilePackage':
        """Generate the PPP as a sequence of encrypted and MACed Command TLVs representing the UPP"""
        inst = cls(metadata=upp.metadata)
        inst.upp = upp
        # store ppk-enc, ppc-mac
        inst.ppk_enc = bsp.c_algo.s_enc
        inst.ppk_mac = bsp.m_algo.s_mac
        inst.initial_mcv = bsp.m_algo.mac_chain
        inst.encoded = bsp.encrypt_and_mac(0x86, upp.to_der())
        return inst

    #def __val__(self):
        #return self.encoded

class BoundProfilePackage(ProfilePackage):
    """Representing a bound profile package (BPP) as defined in SGP.22 Section 2.5.4"""

    @classmethod
    def from_ppp(cls, ppp: ProtectedProfilePackage):
        inst = cls()
        inst.upp = None
        inst.ppp = ppp
        return inst

    @classmethod
    def from_upp(cls, upp: UnprotectedProfilePackage):
        inst = cls()
        inst.upp = upp
        inst.ppp = None
        return inst

    def encode(self, ss: 'RspSessionState', dp_pb: 'CertAndPrivkey') -> bytes:
        """Generate a bound profile package (SGP.22 2.5.4)."""

        def encode_seq(tag: int, sequence: List[bytes]) -> bytes:
            """Encode a "sequenceOfXX" as specified in SGP.22 specifying the raw SEQUENCE OF tag,
            and assuming the caller provides the fully-encoded (with TAG + LEN) member TLVs."""
            payload = b''.join(sequence)
            return bertlv_encode_tag(tag) + bertlv_encode_len(len(payload)) + payload

        bsp = BspInstance.from_kdf(ss.shared_secret, 0x88, 16, ss.host_id, h2b(ss.eid))

        iscr = gen_initialiseSecureChannel(ss.transactionId, ss.host_id, ss.smdp_otpk, ss.euicc_otpk, dp_pb)
        # generate unprotected input data
        conf_idsp_bin = rsp.asn1.encode('ConfigureISDPRequest', {})
        if self.upp:
            smr_bin = self.upp.metadata.gen_store_metadata_request()
        else:
            smr_bin = self.ppp.metadata.gen_store_metadata_request()

        # we don't use rsp.asn1.encode('boundProfilePackage') here, as the BSP already provides
        # fully encoded + MACed TLVs including their tag + length values.  We cannot put those as
        # 'value' input into an ASN.1 encoder, as that would double the TAG + LENGTH :(

        # 'initialiseSecureChannelRequest'
        bpp_seq = rsp.asn1.encode('InitialiseSecureChannelRequest', iscr)
        
        # PQC Extension: Inject ML-KEM ciphertext (tag 0x5F4B) if present
        if hasattr(ss, 'smdp_ct_kem') and ss.smdp_ct_kem:
            logger.debug(f"[PQC] Injecting ML-KEM ciphertext ({len(ss.smdp_ct_kem)} bytes) into InitialiseSecureChannel")
            # We need to inject the 0x5F4B TLV into the BF23 (InitialiseSecureChannelRequest) structure
            # The BF23 structure is already encoded, so we need to decode it, append our TLV, and re-encode
            # For simplicity, we'll append it as raw bytes before the closing of BF23
            # Format: 5F4B [length] [ciphertext]
            ct_tlv = wrap_as_der_tlv(0x5F4B, ss.smdp_ct_kem)
            # Insert the TLV before the end of the BF23 structure
            # BF23 is already complete, so we need to extract its payload, append our TLV, and re-wrap
            # This is tricky, so for now we'll use a simpler approach: modify the signed part
            # Actually, since bpp_seq is the full encoded InitialiseSecureChannelRequest,
            # we can't easily inject into it without re-parsing. Let's modify gen_initialiseSecureChannel instead.
            # For now, store it in iscr and hope the ASN.1 encoder allows unknown fields
            # Or we manually construct the TLV
            
            # Simple approach: parse bpp_seq, inject TLV, reconstruct
            # Since BF23 uses SEQUENCE, we can append after the existing fields
            # Extract payload from BF23 tag
            if bpp_seq[0:2] == bytes([0xBF, 0x23]):
                # Parse length
                offset = 2
                length_byte = bpp_seq[offset]
                offset += 1
                if length_byte & 0x80:
                    num_len_bytes = length_byte & 0x7F
                    length = 0
                    for _ in range(num_len_bytes):
                        length = (length << 8) | bpp_seq[offset]
                        offset += 1
                else:
                    length = length_byte
                
                # Extract existing payload
                payload = bpp_seq[offset:offset+length]
                # Append CT TLV
                new_payload = payload + ct_tlv
                # Reconstruct BF23
                bpp_seq = bertlv_encode_tag(0xBF23) + bertlv_encode_len(len(new_payload)) + new_payload
                logger.debug(f"[PQC] Injected ML-KEM ciphertext, new InitialiseSecureChannel size: {len(bpp_seq)} bytes")
        # firstSequenceOf87
        logger.debug("BPP_ENCODE_DEBUG: Encrypting ConfigureISDP with BSP keys")
        logger.debug(f"BPP_ENCODE_DEBUG: BSP S-ENC: {bsp.c_algo.s_enc.hex()}")
        logger.debug(f"BPP_ENCODE_DEBUG: BSP S-MAC: {bsp.m_algo.s_mac.hex()}")
        bpp_seq += encode_seq(0xa0, bsp.encrypt_and_mac(0x87, conf_idsp_bin))
        # sequenceOF88
        logger.debug("BPP_ENCODE_DEBUG: MAC-only StoreMetadata with BSP keys")
        bpp_seq += encode_seq(0xa1, bsp.mac_only(0x88, smr_bin))

        if self.ppp: # we have to use session keys
            rsk_bin = gen_replace_session_keys(self.ppp.ppk_enc, self.ppp.ppk_mac, self.ppp.initial_mcv)
            # secondSequenceOf87
            bpp_seq += encode_seq(0xa2, bsp.encrypt_and_mac(0x87, rsk_bin))
        else:
            self.ppp = ProtectedProfilePackage.from_upp(self.upp, bsp)

        # 'sequenceOf86'
        bpp_seq += encode_seq(0xa3, self.ppp.encoded)

        # Wrap in BF36 (BoundProfilePackage) for SGP.22 compliance
        # lpac expects: BF36 { BF23 ... A0 ... A1 ... A2 ... A3 ... }
        return bertlv_encode_tag(0xBF36) + bertlv_encode_len(len(bpp_seq)) + bpp_seq

    def decode(self, euicc_ot, eid: str, bpp_bin: bytes):
        """Decode a BPP into the PPP and subsequently UPP. This is what happens inside an eUICC."""

        def split_bertlv_sequence(sequence: bytes) -> List[bytes]:
            remainder = sequence
            ret = []
            while remainder:
                _tag, _l, tlv, remainder = bertlv_return_one_rawtlv(remainder)
                ret.append(tlv)
            return ret

        # we don't use rsp.asn1.decode('boundProfilePackage') here, as the BSP needs
        # fully encoded + MACed TLVs including their tag + length values.
        #bpp = rsp.asn1.decode('BoundProfilePackage', bpp_bin)

        # Since we return raw BPP sequence, use bpp_bin directly
        v = bpp_bin

        # InitialiseSecureChannelRequest
        tag, _l, iscr_bin, remainder = bertlv_return_one_rawtlv(v)
        iscr = rsp.asn1.decode('InitialiseSecureChannelRequest', iscr_bin)

        # configureIsdpRequest
        tag, _l, firstSeqOf87, remainder = bertlv_parse_one_rawtag(remainder)
        if tag != 0xa0:
            raise ValueError("Unexpected 'firstSequenceOf87' tag: %s" % tag)
        firstSeqOf87 = split_bertlv_sequence(firstSeqOf87)

        # storeMetadataRequest
        tag, _l, seqOf88, remainder = bertlv_parse_one_rawtag(remainder)
        if tag != 0xa1:
            raise ValueError("Unexpected 'sequenceOf88' tag: %s" % tag)
        seqOf88 = split_bertlv_sequence(seqOf88)

        tag, _l, tlv, remainder = bertlv_parse_one_rawtag(remainder)
        if tag == 0xa2:
            secondSeqOf87 = split_bertlv_sequence(tlv)
            tag2, _l, seqOf86, remainder = bertlv_parse_one_rawtag(remainder)
            if tag2 != 0xa3:
                raise ValueError("Unexpected 'sequenceOf86' tag: %s" % tag)
            seqOf86 = split_bertlv_sequence(seqOf86)
        elif tag == 0xa3:
            secondSeqOf87 = None
            seqOf86 = split_bertlv_sequence(tlv)
        else:
            raise ValueError("Unexpected 'secondSequenceOf87' tag: %s" % tag)

        # extract smdoOtpk from initialiseSecureChannel
        smdp_otpk = iscr['smdpOtpk']

        # Generate Session Keys using the CRT, opPK.DP.ECKA and otSK.EUICC.ECKA according to annex G
        smdp_public_key = ec.EllipticCurvePublicKey.from_encoded_point(euicc_ot.curve, smdp_otpk)
        self.shared_secret = euicc_ot.exchange(ec.ECDH(), smdp_public_key)

        crt = iscr['controlRefTemplate']
        bsp = BspInstance.from_kdf(self.shared_secret, int.from_bytes(crt['keyType'], 'big'), int.from_bytes(crt['keyLen'], 'big'), crt['hostId'], h2b(eid))

        self.encoded_configureISDPRequest = bsp.demac_and_decrypt(firstSeqOf87)
        self.configureISDPRequest = rsp.asn1.decode('ConfigureISDPRequest', self.encoded_configureISDPRequest)

        self.encoded_storeMetadataRequest = bsp.demac_only(seqOf88)
        self.storeMetadataRequest = rsp.asn1.decode('StoreMetadataRequest', self.encoded_storeMetadataRequest)

        if secondSeqOf87 != None:
            rsk_bin = bsp.demac_and_decrypt(secondSeqOf87)
            rsk = rsp.asn1.decode('ReplaceSessionKeysRequest', rsk_bin)
            # process replace_session_keys!
            bsp = BspInstance(rsk['ppkEnc'], rsk['ppkCmac'], rsk['initialMacChainingValue'])
            self.replaceSessionKeysRequest = rsk

        self.upp = bsp.demac_and_decrypt(seqOf86)
        return self.upp
