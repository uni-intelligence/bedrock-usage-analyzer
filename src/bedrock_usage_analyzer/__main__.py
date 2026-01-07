# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unified CLI entry point for bedrock-usage-analyzer."""

import sys
import logging
import traceback
import argparse

from bedrock_usage_analyzer.utils.paths import (
    get_metadata_location_message,
    get_refresh_location_message,
    get_writable_path,
    get_bundle_path,
    get_data_path,
)

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def cmd_analyze(args):
    """Run usage analysis."""
    from bedrock_usage_analyzer.core.user_inputs import UserInputs
    from bedrock_usage_analyzer.core.analyzer import BedrockAnalyzer
    
    print(get_metadata_location_message())
    print()
    
    user_inputs = UserInputs()
    user_inputs.collect()
    
    # Get output directory (from arg, prompt, or default)
    output_dir = args.output_dir if args.output_dir else user_inputs.select_output_dir()
    
    analyzer = BedrockAnalyzer(user_inputs.region, user_inputs.granularity_config)
    analyzer.analyze(user_inputs.models, output_dir=output_dir)
    
    logger.info(f"\nCompleted! Results saved to: {output_dir}")


def cmd_refresh_regions(args):
    """Refresh regions list."""
    from bedrock_usage_analyzer.sync.regions import refresh_regions
    from bedrock_usage_analyzer.utils.yaml_handler import save_yaml
    
    print(get_refresh_location_message())
    print()
    
    data = refresh_regions()
    output_path = get_writable_path("regions.yml")
    save_yaml(str(output_path), data)
    logger.info(f"✓ Saved: {output_path}")
    
    _maybe_update_bundle(args, "regions.yml", data)


def cmd_refresh_fm_list(args):
    """Refresh FM lists."""
    from bedrock_usage_analyzer.sync.fm_list import refresh_region, refresh_all_regions
    from bedrock_usage_analyzer.utils.yaml_handler import load_yaml
    
    print(get_refresh_location_message())
    print()
    
    if args.region:
        refresh_region(args.region, update_bundle=args.update_bundle)
    else:
        try:
            regions_file = get_data_path('regions.yml')
            regions_data = load_yaml(regions_file)
            regions = regions_data.get('regions', [])
            
            if not regions:
                logger.error("No regions found in regions.yml")
                logger.error("Please run: bua refresh regions")
                sys.exit(1)
            
            logger.info(f"Refreshing {len(regions)} regions...")
            refresh_all_regions(regions, update_bundle=args.update_bundle)
            logger.info("\n✓ All regions refreshed")
            
        except FileNotFoundError:
            logger.error("Regions file not found")
            logger.error("Please run: bua refresh regions")
            sys.exit(1)


def cmd_refresh_fm_quotas(args):
    """Refresh quota mappings."""
    from bedrock_usage_analyzer.sync.quota_mapper import QuotaMapper
    from bedrock_usage_analyzer.utils.ui import select_quota_mapping_params
    
    print(get_refresh_location_message())
    print()
    
    # Use provided arguments or interactive selection
    target_region = args.target_region
    bedrock_region = args.bedrock_region
    model_id = args.model_id
    
    if not bedrock_region or not model_id or not target_region:
        bedrock_region, model_id, target_region = select_quota_mapping_params(
            target_region=target_region,
            bedrock_region=bedrock_region,
            model_id=model_id
        )
    
    mapper = QuotaMapper(bedrock_region, model_id, target_region)
    mapper.run(update_bundle=args.update_bundle)
    
    logger.info("\n✓ Quota mapping complete")


def cmd_refresh_quota_index(args):
    """Generate quota index CSV."""
    from bedrock_usage_analyzer.sync.quota_index import QuotaIndexGenerator
    
    print(get_refresh_location_message())
    print()
    
    generator = QuotaIndexGenerator()
    generator.run(update_bundle=args.update_bundle)
    
    logger.info("\n✓ Quota index generated")


def _maybe_update_bundle(args, filename, data):
    """Update bundled data if --update-bundle flag is set."""
    if not getattr(args, 'update_bundle', False):
        return
    
    from bedrock_usage_analyzer.utils.yaml_handler import save_yaml
    
    bundle_path = get_bundle_path()
    if bundle_path is None:
        logger.error("\nError: --update-bundle requires a development environment.")
        logger.error("       Could not find: ./src/bedrock_usage_analyzer/metadata/")
        logger.error("\nThis flag is for maintainers in a cloned repository.")
        sys.exit(1)
    
    bundle_file = bundle_path / filename
    save_yaml(str(bundle_file), data)
    logger.info(f"✓ Saved: {bundle_file} (bundled)")


def main():
    parser = argparse.ArgumentParser(
        prog='bua',
        description='Bedrock Usage Analyzer - Calculate token usage statistics for Amazon Bedrock'
    )
    subparsers = parser.add_subparsers(dest='command')
    
    # analyze
    p_analyze = subparsers.add_parser('analyze', help='Analyze token usage')
    p_analyze.add_argument('-o', '--output-dir', 
                          help='Directory to save results (default: prompt user)')
    p_analyze.set_defaults(func=cmd_analyze)
    
    # refresh
    p_refresh = subparsers.add_parser('refresh', help='Refresh metadata')
    refresh_sub = p_refresh.add_subparsers(dest='refresh_command')
    
    # refresh regions
    p_regions = refresh_sub.add_parser('regions', help='Refresh regions list')
    p_regions.add_argument('--update-bundle', action='store_true',
                          help='Also update bundled metadata (maintainers only)')
    p_regions.set_defaults(func=cmd_refresh_regions)
    
    # refresh fm-list
    p_fm = refresh_sub.add_parser('fm-list', help='Refresh FM lists')
    p_fm.add_argument('region', nargs='?', help='Specific region (default: all)')
    p_fm.add_argument('--update-bundle', action='store_true',
                     help='Also update bundled metadata (maintainers only)')
    p_fm.set_defaults(func=cmd_refresh_fm_list)
    
    # refresh fm-quotas
    p_quotas = refresh_sub.add_parser('fm-quotas', help='Refresh quota mappings')
    p_quotas.add_argument('target_region', nargs='?', help='Target region')
    p_quotas.add_argument('bedrock_region', nargs='?', help='Bedrock API region')
    p_quotas.add_argument('model_id', nargs='?', help='Model ID for LLM calls')
    p_quotas.add_argument('--update-bundle', action='store_true',
                         help='Also update bundled metadata (maintainers only)')
    p_quotas.set_defaults(func=cmd_refresh_fm_quotas)
    
    # refresh quota-index
    p_index = refresh_sub.add_parser('quota-index', help='Generate quota index CSV')
    p_index.add_argument('--update-bundle', action='store_true',
                        help='Also update bundled metadata (maintainers only)')
    p_index.set_defaults(func=cmd_refresh_quota_index)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == 'refresh' and not getattr(args, 'refresh_command', None):
        p_refresh.print_help()
        sys.exit(1)
    
    try:
        args.func(args)
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
